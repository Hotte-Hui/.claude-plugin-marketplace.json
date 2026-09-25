"""Veyra Bay Klanggenerator (Phase 9): alle Geraeusche prozedural synthetisiert - keine fremden Aufnahmen.

    python vb_audio.py --out <SourceAssets/Export>          (braucht numpy; z. B. mit Blenders Python:)
    blender -b --factory-startup --python Tools/Audio/vb_audio.py -- --out SourceAssets/Export

Schleifen werden im Frequenzraum erzeugt (inverse FFT) und sind dadurch nahtlos; periodische Anteile haben ganze
Perioden je Schleife. Ausgabe: SourceAssets/Export/Audio/SW_VB_<Name>.wav (44.1 kHz, 16 bit, Stereo) + audio.json.
"""

import json
import math
import os
import sys
import wave

import numpy as np

RATE = 44100


def cli_out():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--out" and i + 1 < len(argv):
            return argv[i + 1]
    return os.path.join(os.getcwd(), "SourceAssets", "Export")


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------
def spectral_noise(seconds, rng, low=20.0, high=18000.0, slope=0.0):
    """Nahtlos schleifbares Rauschen mit Bandbegrenzung; slope in dB/Oktave (0 weiss, -3 rosa, -6 braun)."""
    n = int(seconds * RATE)
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    spectrum = rng.normal(size=freqs.size) + 1j * rng.normal(size=freqs.size)
    shape = np.where((freqs >= low) & (freqs <= high), 1.0, 0.0)
    # weiche Bandkanten
    shape *= np.clip((freqs - low * 0.7) / (low * 0.3 + 1e-9), 0, 1) * np.clip((high * 1.3 - freqs) / (high * 0.3), 0, 1)
    with np.errstate(divide="ignore"):
        tilt = np.where(freqs > 0, (freqs / 1000.0) ** (slope / 6.02), 0.0)
    signal = np.fft.irfft(spectrum * shape * tilt, n)
    return signal / (np.max(np.abs(signal)) + 1e-9)


def periodic_env(n, cycles, rng, sharpness=1.0, floor=0.0):
    """Huellkurve mit ganzzahligen Zyklen je Schleife (nahtlos)."""
    t = np.arange(n) / n
    env = np.zeros(n)
    for k in range(1, 4):
        env += rng.uniform(0.3, 1.0) / k * np.sin(2 * np.pi * cycles * k * t + rng.uniform(0, 2 * np.pi))
    env = (env - env.min()) / (env.max() - env.min() + 1e-9)
    return floor + (1 - floor) * env ** sharpness


def place(buffer, sound, start):
    """Klang zyklisch in einen Schleifenpuffer mischen."""
    n = buffer.shape[0]
    idx = (np.arange(sound.shape[0]) + start) % n
    np.add.at(buffer, idx, sound)


def decay_burst(length_s, freq, rng, decay=30.0, noise=0.0):
    n = int(length_s * RATE)
    t = np.arange(n) / RATE
    tone = np.sin(2 * np.pi * freq * t + rng.uniform(0, 6.28))
    if noise:
        tone = (1 - noise) * tone + noise * rng.normal(size=n)
    return tone * np.exp(-decay * t)


def lowpass(x, cutoff):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / RATE)
    spec *= 1.0 / (1.0 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, x.size)


def stereo(left, right=None, width=0.0, rng=None):
    if right is None:
        if width > 0 and rng is not None:
            shift = int(width * RATE * 0.02)
            right = np.roll(left, shift)
        else:
            right = left
    return np.stack([left, right], axis=-1)


def normalize(x, peak=0.9):
    return x * (peak / (np.max(np.abs(x)) + 1e-9))


def fade(data, fade_in=0.002, fade_out=0.03):
    """Einzelklaenge weich ein-/ausblenden (kein Knacken am Ende)."""
    n = data.shape[0]
    ramp_in = np.minimum(1.0, np.arange(n) / max(fade_in * RATE, 1.0))
    ramp_out = np.minimum(1.0, (n - 1 - np.arange(n)) / max(fade_out * RATE, 1.0))
    return data * (ramp_in * ramp_out)[:, None]


def write_wav(path, data):
    data = np.clip(data, -1.0, 1.0)
    if data.ndim == 1:
        data = data[:, None]
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(path, "wb") as handle:
        handle.setnchannels(pcm.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())


# ---------------------------------------------------------------------------
# Klaenge
# ---------------------------------------------------------------------------
def rain(rng, heavy):
    seconds = 12.0
    n = int(seconds * RATE)
    base = spectral_noise(seconds, rng, 400.0, 12000.0, -1.5) * (0.5 if heavy else 0.25)
    if heavy:
        base += spectral_noise(seconds, rng, 60.0, 400.0, -3.0) * 0.25
    out = np.zeros((n, 2))
    out[:, 0] = base
    out[:, 1] = np.roll(base, 997)
    drops = 2600 if heavy else 700
    for _ in range(drops):
        drop = decay_burst(rng.uniform(0.008, 0.03), rng.uniform(1800, 6500), rng, decay=rng.uniform(150, 400), noise=0.5)
        drop *= rng.uniform(0.05, 0.35)
        pan = rng.uniform(0, 1)
        start = rng.integers(0, n)
        place(out[:, 0], drop * (1 - pan), start)
        place(out[:, 1], drop * pan, start)
    return normalize(out, 0.7 if heavy else 0.5), True


def wind(rng):
    seconds = 16.0
    n = int(seconds * RATE)
    left = spectral_noise(seconds, rng, 40.0, 900.0, -4.5)
    right = spectral_noise(seconds, rng, 40.0, 900.0, -4.5)
    env = periodic_env(n, 2, rng, 1.6, 0.25)
    whistle = spectral_noise(seconds, rng, 700.0, 1400.0, 0.0) * periodic_env(n, 3, rng, 3.0, 0.0) * 0.15
    return normalize(np.stack([left * env + whistle, right * env + whistle], axis=-1), 0.7), True


def sea(rng):
    seconds = 24.0
    n = int(seconds * RATE)
    swell = periodic_env(n, 3, rng, 2.2, 0.15)
    body = spectral_noise(seconds, rng, 60.0, 1500.0, -3.0)
    wash = spectral_noise(seconds, rng, 1500.0, 9000.0, -1.0) * np.roll(swell, int(0.8 * RATE)) ** 2 * 0.5
    left = body * swell + wash
    right = np.roll(body, 3001) * swell + np.roll(wash, 1500)
    return normalize(np.stack([left, right], axis=-1), 0.65), True


def city(rng):
    seconds = 20.0
    n = int(seconds * RATE)
    hum = spectral_noise(seconds, rng, 30.0, 300.0, -4.0) * 0.8
    traffic = spectral_noise(seconds, rng, 200.0, 3000.0, -3.0) * periodic_env(n, 4, rng, 1.5, 0.3) * 0.4
    out = stereo(hum + traffic, np.roll(hum, 4410) + np.roll(traffic, 2205))
    for _ in range(3):   # ferne Hupen / Rufe
        length = rng.uniform(0.2, 0.6)
        t = np.arange(int(length * RATE)) / RATE
        f = rng.uniform(380, 520)
        horn = (np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + np.sin(2 * np.pi * f * 1.26 * t) * 0.3)
        horn = lowpass(horn * np.minimum(1, t * 30) * np.exp(-2 * t), 1500.0) * 0.08
        start = rng.integers(0, n)
        pan = rng.uniform(0.2, 0.8)
        place(out[:, 0], horn * (1 - pan), start)
        place(out[:, 1], horn * pan, start)
    return normalize(out, 0.5), True


def birds(rng):
    seconds = 20.0
    n = int(seconds * RATE)
    out = np.zeros((n, 2))
    for _ in range(38):
        start = rng.integers(0, n)
        pan = rng.uniform(0, 1)
        f0, f1 = rng.uniform(2200, 4200), rng.uniform(3000, 6500)
        for k in range(rng.integers(2, 6)):
            length = rng.uniform(0.04, 0.14)
            t = np.arange(int(length * RATE)) / RATE
            freq = np.linspace(f0, f1, t.size) * (1 + 0.05 * np.sin(2 * np.pi * 40 * t))
            phase = 2 * np.pi * np.cumsum(freq) / RATE
            chirp = np.sin(phase) * np.sin(np.pi * t / length) ** 2 * rng.uniform(0.1, 0.35)
            place(out[:, 0], chirp * (1 - pan), start + int(k * rng.uniform(0.08, 0.2) * RATE))
            place(out[:, 1], chirp * pan, start + int(k * rng.uniform(0.08, 0.2) * RATE))
    out += stereo(spectral_noise(seconds, rng, 150.0, 1200.0, -3.0) * 0.02)
    return normalize(out, 0.45), True


def crickets(rng):
    seconds = 8.0
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for voice in range(5):
        f = rng.uniform(4300, 5200)
        f = round(f * seconds) / seconds                   # ganze Perioden
        pulse = (np.sin(2 * np.pi * 30 * t + voice) > 0.3).astype(float)
        chirps = (np.sin(2 * np.pi * rng.integers(1, 3) / seconds * 4 * t + rng.uniform(0, 6)) > 0.2).astype(float)
        tone = np.sin(2 * np.pi * f * t) * pulse * chirps * rng.uniform(0.2, 0.5)
        pan = rng.uniform(0, 1)
        out[:, 0] += tone * (1 - pan)
        out[:, 1] += tone * pan
    out += stereo(spectral_noise(seconds, rng, 100.0, 800.0, -3.0) * 0.01)
    return normalize(out, 0.35), True


def thunder(rng):
    seconds = 7.0
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    crack = spectral_noise(seconds, rng, 200.0, 8000.0, -1.0) * np.exp(-t * 18.0) * 0.8
    rumble_l = spectral_noise(seconds, rng, 20.0, 220.0, -5.0)
    rumble_r = spectral_noise(seconds, rng, 20.0, 220.0, -5.0)
    env = np.minimum(1.0, t / 0.25) * np.exp(-t / 2.2) * (0.6 + 0.4 * periodic_env(n, 9, rng, 1.2, 0.0))
    return normalize(np.stack([crack * 0.7 + rumble_l * env, crack + rumble_r * env], axis=-1), 0.95), False


def engine(rng):
    """Motor-Schleife bei 2000 U/min (4 Zylinder: Zuendfrequenz 66.7 Hz). Ganze Perioden in 3 s."""
    seconds = 3.0
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    fire = 200.0 / 3.0                                     # 66.67 Hz -> 200 Perioden in 3 s
    signal = np.zeros(n)
    for k in range(1, 14):
        amp = 1.0 / k ** 0.9 * (1.3 if k in (2, 4) else 1.0)
        signal += amp * np.sin(2 * np.pi * fire * k * t + rng.uniform(0, 6.28))
    signal += 0.35 * np.sin(2 * np.pi * fire * 0.5 * t)    # halbe Ordnung (Motorcharakter)
    mech = spectral_noise(seconds, rng, 300.0, 5000.0, -3.0) * (0.6 + 0.4 * np.sin(2 * np.pi * fire * t))
    intake = spectral_noise(seconds, rng, 80.0, 600.0, -3.0) * 0.3
    mono = lowpass(signal * 0.6 + mech * 0.25 + intake, 3500.0)
    return normalize(stereo(mono, np.roll(mono, 40)), 0.8), True


def tires(rng):
    seconds = 4.0
    road = spectral_noise(seconds, rng, 150.0, 2000.0, -3.0)
    return normalize(stereo(road, np.roll(road, 700)), 0.6), True


def horn(rng):
    seconds = 1.0
    t = np.arange(int(seconds * RATE)) / RATE
    tone = np.zeros_like(t)
    for f in (420.0, 530.0):
        tone += np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sin(2 * np.pi * f * 2 * t) * 0.2
    return normalize(stereo(lowpass(tone, 2500.0)), 0.7), True


def indicator(rng):
    n = int(0.667 * RATE)
    out = np.zeros(n)
    for start, f in ((int(0.01 * RATE), 3200.0), (int(0.37 * RATE), 2600.0)):
        click = decay_burst(0.012, f, rng, decay=500.0, noise=0.6)
        out[start:start + click.size] += click
    return normalize(stereo(out), 0.5), True


def footstep(rng, variant):
    n = int(0.3 * RATE)
    t = np.arange(n) / RATE
    heel = spectral_noise(0.3, rng, 80.0, 2500.0, -3.0) * np.exp(-t * 60.0)
    scuff = spectral_noise(0.3, rng, 1500.0, 7000.0, -1.0) * np.exp(-np.maximum(t - 0.03, 0) * 40.0) * (t > 0.02) * 0.3
    low = decay_burst(0.3, 70.0 + variant * 12.0, rng, decay=45.0) * 0.5
    return normalize(stereo(heel + scuff + low), 0.8), False


def car_door(rng):
    n = int(0.6 * RATE)
    t = np.arange(n) / RATE
    thud = decay_burst(0.6, 75.0, rng, decay=14.0) + spectral_noise(0.6, rng, 40.0, 400.0, -3.0) * np.exp(-t * 20.0)
    latch = np.zeros(n)
    click = decay_burst(0.02, 2800.0, rng, decay=300.0, noise=0.5)
    latch[int(0.02 * RATE):int(0.02 * RATE) + click.size] = click * 0.5
    return normalize(stereo(thud + latch), 0.9), False


def ui_click(rng):
    return normalize(stereo(decay_burst(0.05, 1800.0, rng, decay=120.0, noise=0.2)), 0.5), False


def street_music(rng):
    """Strassenmusiker: Gitarre (Karplus-Strong), eigene Akkordfolge, 16 s Schleife (Am - F - C - G)."""
    seconds = 16.0
    n = int(seconds * RATE)
    out = np.zeros(n)

    def pluck(freq, length, damping=0.996):
        period = int(RATE / freq)
        buf = rng.uniform(-1, 1, period)
        samples = np.zeros(int(length * RATE))
        for i in range(samples.size):
            samples[i] = buf[i % period]
            buf[i % period] = damping * 0.5 * (buf[i % period] + buf[(i + 1) % period])
        return samples

    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    beat = seconds / 16.0
    for bar, chord in enumerate(chords):
        for step in range(4):
            start = int((bar * 4 + step) * beat * RATE)
            pattern = [chord[0] / 2, chord[1], chord[2], chord[1]] if step % 2 == 0 else [chord[2], chord[1], chord[0], chord[2]]
            for k, f in enumerate(pattern):
                note = pluck(f, 1.2) * (0.5 if k else 0.7)
                place(out, note, start + int(k * beat / 4 * RATE))
    return normalize(stereo(out, np.roll(out, 300)), 0.6), True


def main():
    out_root = os.path.abspath(cli_out())
    folder = os.path.join(out_root, "Audio")
    os.makedirs(folder, exist_ok=True)
    rng = np.random.default_rng(7)
    sounds = {
        "RainLight": lambda: rain(rng, False),
        "RainHeavy": lambda: rain(rng, True),
        "Wind": lambda: wind(rng),
        "Sea": lambda: sea(rng),
        "City": lambda: city(rng),
        "Birds": lambda: birds(rng),
        "Crickets": lambda: crickets(rng),
        "Thunder_1": lambda: thunder(rng),
        "Thunder_2": lambda: thunder(rng),
        "Thunder_3": lambda: thunder(rng),
        "Engine": lambda: engine(rng),
        "Tires": lambda: tires(rng),
        "Horn": lambda: horn(rng),
        "Indicator": lambda: indicator(rng),
        "Footstep_1": lambda: footstep(rng, 0),
        "Footstep_2": lambda: footstep(rng, 1),
        "Footstep_3": lambda: footstep(rng, 2),
        "Footstep_4": lambda: footstep(rng, 3),
        "CarDoor": lambda: car_door(rng),
        "UIClick": lambda: ui_click(rng),
        "StreetMusic": lambda: street_music(rng),
    }
    meta = {}
    for name, make in sounds.items():
        data, looping = make()
        if not looping:
            data = fade(data)
        path = os.path.join(folder, "SW_VB_%s.wav" % name)
        write_wav(path, data)
        meta["SW_VB_%s" % name] = {"looping": looping, "seconds": round(data.shape[0] / RATE, 3)}
        print("%-22s %5.2f s %s" % (name, data.shape[0] / RATE, "Schleife" if looping else ""))
    with open(os.path.join(folder, "audio.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
