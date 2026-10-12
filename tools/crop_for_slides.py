"""
crop_for_slides.py — cut the key areas out of the full-page screenshots
(screenshots/*.png) into screenshots/slides/*.png for the presentation.
Fixed areas use pixel coordinates of the 1920-px-wide captures; the impact and
audit areas end at the grey divider above "Audit trail", found automatically
(page height varies with each scenario). Full-page captures stay untouched.
Run:  py -3.11 tools/crop_for_slides.py
"""
import os, glob
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(HERE, "screenshots")
OUT  = os.path.join(SRC, "slides")

PROPOSAL = (70, 933, 1848, 1480)     # "Proposed change" + validation line
IMPACT_TOP = 1499                    # "Impact simulation" title

def src(prefix):
    return Image.open(glob.glob(os.path.join(SRC, prefix + "_*.png"))[0]).convert("RGB")

def divider(img, start):
    """y of the full-width grey rule that separates the result from the audit trail."""
    px = img.load()
    for y in range(start, img.height):
        row = [px[x, y] for x in range(150, 1750, 25)]
        if len(set(row)) == 1 and 200 <= row[0][0] <= 235 \
           and abs(row[0][1] - row[0][0]) <= 3 and abs(row[0][2] - row[0][0]) <= 6:   # grey, not a tinted box
            # the divider is followed by blank space (table borders are not)
            below = {px[x, yy] for yy in range(y + 5, min(img.height, y + 40)) for x in range(150, 1750, 50)}
            if below == {(255, 255, 255)}:
                return y
    return img.height

def save(img, box, name):
    img.crop(box).save(os.path.join(OUT, name + ".png"))
    print("saved", name, box)

def main():
    os.makedirs(OUT, exist_ok=True)
    data = src("02")
    save(data, (76, 220, 1846, 819), "data_overview")
    save(data, (82, 838, 1134, 1650), "data_distribution")
    for prefix, name in [("03", "applied"), ("06", "warning"), ("08", "overlap")]:
        img = src(prefix)
        if prefix == "03":
            save(img, (70, 290, 1848, 908), "home_request")
            save(img, PROPOSAL, "proposal")
        save(img, (70, IMPACT_TOP, 1848, divider(img, IMPACT_TOP) - 25), "impact_" + name)
    audit = src("14")
    top = divider(audit, 950)
    save(audit, (70, top + 20, 1848, min(audit.height, top + 430)), "audit_trail")

if __name__ == "__main__":
    main()
