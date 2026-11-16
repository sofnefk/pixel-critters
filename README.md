# Pixel Critters 🦋

An interactive, animated desktop background built with **Python** and **Pygame** for Windows.

Pixel Critters brings a little life to an otherwise ordinary desktop. Tiny pixel-art creatures wander around the screen, leave glowing trails, and react to the movement of your mouse. You can switch between different species, watch them interact with their surroundings, or simply let them do their thing in the background.

![Pixel Critters in action](assets/critters-demo.gif)

## ✨ Features

- **Six animated species:** butterflies, jellyfish, dragonflies, koi, frogs, and crabs.
- **Interactive movement:** creatures react when the cursor gets close.
- **Click effects:** clicking the screen scatters nearby creatures and creates ripples.
- **Pixel trails:** movement leaves behind fading, glowing trails.
- **Automatic switching:** species can change periodically.
- **Desktop wallpaper mode:** runs behind the desktop icons.
- **Lock-screen snapshots:** generate a still image of your favourite species.

## 🛠️ Built With

- Python
- Pygame
- Windows API (`ctypes`)

## 🚀 Getting Started

### Requirements

- Windows 10 or Windows 11
- Python 3
- Pygame

### Installation

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/pixel-critters.git
cd pixel-critters
```

Create and activate a virtual environment:

```bash
py -m venv .venv
.venv\Scripts\activate
```

Install the dependencies:

```bash
py -m pip install -r requirements.txt
```

### Running Pixel Critters

**Preview mode** — open the animation in a normal window:

```bash
py pixel_critters.py
```

**Wallpaper mode** — place the animation behind your desktop icons:

```bash
py pixel_critters.py wallpaper
```

**Snapshot mode** — generate a still image for your lock screen:

```bash
py pixel_critters.py snapshot koi
```

Replace `koi` with another species to generate a different image.

## ⌨️ Controls

| Shortcut | Action |
|---|---|
| `Ctrl + Alt + →` | Next species |
| `Ctrl + Alt + ←` | Previous species |
| `Ctrl + Alt + Q` | Quit |
| `Esc` | Quit preview mode |

Move your cursor near the creatures to make them scatter. Click to create an extra burst of movement and ripples.

## 💭 A Little Personal Background

This project started as a small experiment in Python, but it became something a little more personal.

My dad has always had an interest in coding, and even built his own website for his café back in 2013. When I showed him Pixel Critters, he immediately recognised the sprites and started telling me about experimenting with sprites himself in the late 1980s. His father had brought him a huge programming book from the States, and he spent time playing around with what he could create.

He was genuinely excited to see what I was making, praised the project, and even gave me a few ideas. It was lovely to discover that something I was exploring as a beginner had a little connection to his own experiences with programming decades earlier.

---

*An experiment in code, creativity, and tiny pixel creatures.*
