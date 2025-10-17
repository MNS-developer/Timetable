KFUEIT Timetable Combiner

This project automatically extracts and combines **hundreds of individual timetable HTML files** (downloaded from KFUEIT) into a single **interactive and searchable webpage**.

You can search the generated timetable by:
- **Class**
- **Teacher**
- **Course**
- **Room**

---

## Features

Automatically parses all `.html` files inside the `course_htmls/` folder  
Detects and normalizes room formats like `COSC.1.05R`, `TB.2.14L`, etc.  
Builds `combined_timetable.html` — an offline, searchable webpage  
Uses **Bootstrap 5** + **Bootstrap-Select** for modern responsive UI

---

## NOTE
Python ≥3.8 is recommended

---

## Dependencies

To run this project, install the following Python libraries:

```bash
pip install beautifulsoup4


