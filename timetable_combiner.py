import os
from bs4 import BeautifulSoup
from collections import defaultdict
import re
import json

INPUT_DIR = "course_htmls"
OUTPUT_FILE = "all_timetables.html"


def time_to_min(t):
    """Convert HH:MM to minutes."""
    h, m = map(int, t.split(':'))
    return h * 60 + m


def extract_tables():
    """Parse all class timetables and collect teacher, course, and room schedules (rowspan-safe)."""
    class_tables = {}
    teacher_blocks = defaultdict(lambda: defaultdict(list))
    course_blocks = defaultdict(lambda: defaultdict(list))
    room_blocks = defaultdict(lambda: defaultdict(list))

    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".html"):
            continue

        filepath = os.path.join(INPUT_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        # extract class name
        heading = soup.find("p", string=re.compile("Class:"))
        class_name = heading.get_text().split("Class:")[-1].strip() if heading else filename

        # get timetable
        table = soup.find("table", {"class": "time_table"})
        if not table:
            continue

        class_tables[class_name] = str(table)

        header_row = table.find_all("tr")[1]
        day_headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
        body_rows = table.find_all("tr")[2:]
        rowspan_tracker = [0] * len(day_headers)

        for row in body_rows:
            cells = row.find_all("td")
            col_idx = 0

            for cell in cells:
                while col_idx < len(rowspan_tracker) and rowspan_tracker[col_idx] > 0:
                    rowspan_tracker[col_idx] -= 1
                    col_idx += 1

                if "lightgreen" in cell.get("class", []):
                    block_text = cell.get_text("\n", strip=True)
                    lines = [line.strip() for line in block_text.split("\n") if line.strip()]
                    if len(lines) < 4:
                        col_idx += 1
                        continue

                    course_name = lines[0]
                    course_match = re.match(r"^[A-Z]{3,5}-\d{3,4}-[A-Za-z0-9 ]+", course_name)
                    if not course_match:
                        col_idx += 1
                        continue

                    i = 1
                    teachers = []
                    while i < len(lines) and any(prefix in lines[i] for prefix in ["Engr.", "Dr.", "Ms.", "Mr."]):
                        teachers.append(lines[i])
                        i += 1

                    if not teachers:
                        col_idx += 1
                        continue

                    room = lines[i] if i < len(lines) else "Unknown Room"
                    i += 1

                    time_range = lines[i] if i < len(lines) else "Unknown"
                    if not re.match(r"\d{2}:\d{2}\s*-\s*\d{2}:\d{2}", time_range):
                        col_idx += 1
                        continue

                    day = day_headers[col_idx] if col_idx < len(day_headers) else "Unknown"

                    # Reconstruct block_text to standardize
                    reconstructed = f"{course_name}\n" + "\n".join(teachers) + f"\n{room}\n{time_range}"
                    content = f"{reconstructed}\n[{class_name}]"

                    for teacher in teachers:
                        teacher_blocks[teacher][day].append((time_range, content))

                    # Append once for course and room
                    course_blocks[course_name][day].append((time_range, content))
                    room_blocks[room][day].append((time_range, content))

                rowspan = int(cell.get("rowspan", 1))
                if rowspan > 1 and col_idx < len(rowspan_tracker):
                    rowspan_tracker[col_idx] = rowspan - 1

                col_idx += 1

    return class_tables, teacher_blocks, course_blocks, room_blocks


def build_generic_tables(data_blocks, label):
    """Build KFUEIT-style HTML tables for teachers, courses, or rooms using fixed time grid and rowspan."""
    tables = {}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    fixed_times = ["09:00", "10:30", "12:00", "13:30", "15:00"]
    slot_starts = [time_to_min(t) for t in fixed_times]
    slot_size = 90  # minutes per slot

    for key, day_blocks in data_blocks.items():
        header_row = "<tr class='time_table_heading'><th class='corner_box'><p>Day</p><span>Time</span></th>" + "".join(
            f"<th>{day}</th>" for day in days
        ) + "</tr>"

        # Process blocks per day: parse times and sort
        processed_day_blocks = {}
        for day in days:
            blocks = day_blocks.get(day, [])
            parsed_blocks = []
            for time_range, content in blocks:
                if not re.match(r"\d{2}:\d{2}\s*-\s*\d{2}:\d{2}", time_range):
                    continue
                start_str, end_str = re.split(r"\s*-\s*", time_range)
                start_min = time_to_min(start_str)
                end_min = time_to_min(end_str)
                parsed_blocks.append({'start_min': start_min, 'end_min': end_min, 'start_str': start_str, 'content': content})
            parsed_blocks.sort(key=lambda x: x['start_min'])
            processed_day_blocks[day] = parsed_blocks

        # Build rows with rowspan tracking
        rowspan_tracker = [0] * len(days)
        rows_html = ""
        for slot_idx, start_time in enumerate(fixed_times):
            current_start_min = slot_starts[slot_idx]
            row_cells = [f"<td class='timeside'><p>{start_time}</p></td>"]
            for d, day in enumerate(days):
                if rowspan_tracker[d] > 0:
                    rowspan_tracker[d] -= 1
                    continue  # Skip cell, covered by previous rowspan

                blocks_this_day = processed_day_blocks[day]
                starting_blocks = [b for b in blocks_this_day if b['start_min'] == current_start_min]

                # Handle Friday prayer break if no block and it's the 13:30 slot on Friday
                if not starting_blocks and day == "Friday" and start_time == "13:30":
                    row_cells.append("<td rowspan=1 class='breaktime'><br>Friday Prayer<br/>13:30 - 14:00</td>")
                    continue

                if not starting_blocks:
                    row_cells.append("<td class='fixedheight'> --- </td>")
                    continue

                # Assume all starting blocks have same duration
                duration = starting_blocks[0]['end_min'] - current_start_min
                rowspan = duration // slot_size

                # Collect contents and merge as before
                contents = [b['content'] for b in starting_blocks]
                merged = defaultdict(list)
                for content in contents:
                    title = content.split("\n")[0]
                    merged[title].append(content)

                cell_html = ""
                for title, all_contents in merged.items():
                    if len(all_contents) == 1:
                        formatted = all_contents[0].replace("\n", "<br/>")
                        cell_html += f"<div class='neon-block'>{formatted}</div>"
                    else:
                        combined = {}
                        for content in all_contents:
                            parts = content.strip().split("\n")
                            if len(parts) < 5:
                                continue
                            class_part = parts[-1]
                            time_text = parts[-2]
                            room = parts[-3]
                            subject = parts[0]
                            name_lines = parts[1:-3]
                            name_line = ", ".join(name_lines)
                            key_tuple = (subject, name_line, room, time_text)
                            combined.setdefault(key_tuple, []).append(class_part)

                        formatted_blocks = []
                        for (subject, name_line, room, time_text), classes in combined.items():
                            class_lines = "<br/>".join(classes)
                            name_display = name_line.replace(", ", "<br/>")
                            formatted_blocks.append(
                                f"{subject}<br/>{name_display}<br/>{room}<br/>{time_text}<br/>{class_lines}"
                            )

                        joined_blocks = "<hr style='margin:4px 0;border-top:1px dashed #00b7eb;'/>".join(formatted_blocks)
                        formatted_block = f"""
                        <div class='neon-block' style="position:relative;padding:3px;">
                            {joined_blocks}
                            <span class="badge badge-primary"
                                  style="position:absolute;top:2px;right:2px;background:#26a69a;">×{len(all_contents)}</span>
                        </div>
                        """
                        cell_html += formatted_block

                # Add the td with rowspan and lightgreen class
                row_cells.append(f"<td rowspan={rowspan} class='lightgreen'>{cell_html}</td>")

                if rowspan > 1:
                    rowspan_tracker[d] = rowspan - 1

            rows_html += "<tr>" + "".join(row_cells) + "</tr>"

        table_html = f"""
        <table class="table table-bordered time_table" width="100%">
            <tr><td colspan="8">
            <h3 align="center" class="kf_heading">KFUEIT Time Table</h3>
            <div class="kf_p"><p align="center">{label}: {key}</p></div>
            </td></tr>
            {header_row}
            {rows_html}
        </table>
        """
        tables[key] = table_html

    return tables


def build_html(class_tables, teacher_tables, course_tables, room_tables):
    class_options = "".join([f"<option value='{c}'>{c}</option>" for c in sorted(class_tables)])
    teacher_options = "".join([f"<option value='{t}'>{t}</option>" for t in sorted(teacher_tables)])
    course_options = "".join([f"<option value='{c}'>{c}</option>" for c in sorted(course_tables)])
    room_options = "".join([f"<option value='{r}'>{r}</option>" for r in sorted(room_tables)])

    futuristic_css = """
    body {
        background-color: #0a0a0a;
        color: #ffffff;
        font-family: 'Orbitron', sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 20px;
        min-height: 100vh;
    }
    h2, .kf_heading {
        color: #00b7eb;
        text-shadow: 0 0 10px #00b7eb;
        text-align: center;
    }
    .kf_p p {
        color: #26a69a;
        font-size: 15px;
        text-align: center;
    }
    .table.table-bordered.time_table td, 
    .table.table-bordered.time_table th {
        padding: 0px;
        transition: all 0.3s ease;
        text-align: center;
    }
    .time_table td, .time_table th { 
        text-align: center; 
        vertical-align: middle; 
        padding: 8px; 
        font-size: 0.9rem;
    }
    .time_table { 
        width: 100%; 
        max-width: 100%;
        margin: 20px 0; 
        border: 1px solid #00b7eb; 
        background: #102027; 
        box-shadow: 0 0 20px rgba(0, 183, 235, 0.3);
        animation: pulse 2s infinite;
        table-layout: auto;
    }

    .breaktime { 
        background: #2a0a0a; 
    }
    .time_table_heading th { 
        background: linear-gradient(19deg, #00b7eb, #26a69a); 
        color: #ffffff; 
        font-size: 0.9rem; 
        text-align: center; 
    }
    .timeside { 
        background: #26a69a; 
        color: #ffffff; 
        height: 60px; 
    }
    .timeside p { 
        margin: 0; 
        font-size: 0.9rem; 
        font-weight: bold; 
        color: #ffffff; 
    }
    .corner_box { 
        background: linear-gradient(19deg, #00b7eb, #26a69a); 
        color: #ffffff; 
    }
    .form-control {
        background: #102027;
        color: #00b7eb;
        border: 1px solid #00b7eb;
    }
    .bootstrap-select .btn {
        background: #102027;
        color: #00b7eb;
        border: 1px solid #00b7eb;
    }
    .bootstrap-select .dropdown-menu {
        background: #102027;
        z-index: 2000;
    }
    .bootstrap-select .dropdown-item {
        color: #00b7eb;
    }
    .bootstrap-select .dropdown-item:hover {
        background: #00b7eb;
        color: #ffffff;
    }
    #timetableArea {
        opacity: 0;
        transition: opacity 0.5s ease-in-out;
        width: 100%;
        z-index: 1000;
    }
    #timetableArea.visible {
        opacity: 1;
    }
    .form-row {
        width: 100%;
        max-width: 1200px;
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        justify-content: center;
        z-index: 2000;
        position: relative;
    }
    .col-md-3 {
        flex: 1 1 200px;
        max-width: 300px;
    }
    @media (max-width: 768px) {
        .time_table td, .time_table th {
            font-size: 0.7rem;
            padding: 5px;
        }
        .neon-block {
            font-size: 0.7rem;
        }
        .col-md-3 {
            flex: 1 1 100%;
            max-width: 100%;
        }
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 rgba(0, 183, 235, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(0, 183, 235, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 183, 235, 0); }
    }
    .animate__animated {
        --animate-duration: 1s;
    }
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>All KFUEIT Timetables</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css" />
        <link rel="stylesheet" href="https://my.kfueit.edu.pk/assets/dist/bootstrap.min.css" />
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-select@1.13.18/dist/css/bootstrap-select.min.css">
        <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap-select@1.13.18/dist/js/bootstrap-select.min.js"></script>
        <style>{futuristic_css}</style>
    </head>
    <body>
        <h2 class="animate__animated animate__fadeInDown">All KFUEIT Timetables</h2>
        <div class="form-row animate__animated animate__fadeIn">
            <div class="col-md-3">
                <label>Select Class</label>
                <select id="classSelect" class="form-control selectpicker" data-live-search="true">
                    <option value="">-- Choose Class --</option>
                    {class_options}
                </select>
            </div>
            <div class="col-md-3">
                <label>Select Teacher</label>
                <select id="teacherSelect" class="form-control selectpicker" data-live-search="true">
                    <option value="">-- Choose Teacher --</option>
                    {teacher_options}
                </select>
            </div>
            <div class="col-md-3">
                <label>Select Course</label>
                <select id="courseSelect" class="form-control selectpicker" data-live-search="true">
                    <option value="">-- Choose Course --</option>
                    {course_options}
                </select>
            </div>
            <div class="col-md-3">
                <label>Select Room</label>
                <select id="roomSelect" class="form-control selectpicker" data-live-search="true">
                    <option value="">-- Choose Room --</option>
                    {room_options}
                </select>
            </div>
        </div>
        <hr style="border-color: #00b7eb; width: 100%; max-width: 1200px;">
        <div id="timetableArea"></div>

        <script>
            $(document).ready(function() {{
                $('.selectpicker').selectpicker();

                function showTable(val, tables) {{
                    const area = $('#timetableArea');
                    area.removeClass('visible animate__animated animate__fadeIn');
                    area.html(tables[val] || "");
                    setTimeout(() => {{
                        area.addClass('animate__animated animate__fadeIn');
                        area.addClass('visible');
                    }}, 100);

                    // Reset other selectpickers to ensure they remain functional
                    $('.selectpicker').not(this).each(function() {{
                        $(this).val('').selectpicker('refresh');
                    }});
                }}

                $('#classSelect').on('changed.bs.select', function() {{
                    showTable($(this).val(), classTables);
                }});

                $('#teacherSelect').on('changed.bs.select', function() {{
                    showTable($(this).val(), teacherTables);
                }});

                $('#courseSelect').on('changed.bs.select', function() {{
                    showTable($(this).val(), courseTables);
                }});

                $('#roomSelect').on('changed.bs.select', function() {{
                    showTable($(this).val(), room_tables);
                }});
            }});

            const classTables = {json.dumps(class_tables)};
            const teacherTables = {json.dumps(teacher_tables)};
            const courseTables = {json.dumps(course_tables)};
            const room_tables = {json.dumps(room_tables)};
        </script>
    </body>
    </html>
    """
    return html


def main():
    print("Extracting tables...")
    class_tables, teacher_blocks, course_blocks, room_blocks = extract_tables()
    print(f"Found {len(class_tables)} classes, {len(teacher_blocks)} teachers, {len(course_blocks)} courses, and {len(room_blocks)} rooms.")

    print("Building timetables...")
    teacher_tables = build_generic_tables(teacher_blocks, "Teacher")
    course_tables = build_generic_tables(course_blocks, "Course")
    room_tables = build_generic_tables(room_blocks, "Room")

    print("Generating HTML...")
    final_html = build_html(class_tables, teacher_tables, course_tables, room_tables)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"✅ Done! Open {OUTPUT_FILE} in your browser.")


if __name__ == "__main__":
    main()