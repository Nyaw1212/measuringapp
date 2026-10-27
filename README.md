# Measuring App — v0.1

A Python desktop photo-measurement prototype.

## Install and launch (Windows PowerShell)

```powershell
git clone https://github.com/Nyaw1212/measuringapp.git
cd measuringapp
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Workflow
1. Open a JPG, PNG, BMP, or WebP photo.
2. Enter a **known reference distance** (e.g. a 3 m wall).
3. Click **Calibrate: 2 Points**; click its two endpoints in the photo.
4. Click **Measure: A–B** and click two endpoints; values are saved as Measure A, B, C, etc.
5. Mouse-wheel zoom; **Fit Photo** to see the entire image.

Zoom and window resize do not affect measured distances, because points are stored in original image coordinates.

## Limitation
This first version assumes that reference and measured dimensions are on the same approximately front-facing plane with uniform scale. **Isometric/perspective correction is not implemented yet.** It should be a separate feature: identify a wall plane (ideally four corners), rectify perspective, and calibrate the rectified plane to known physical dimensions.
