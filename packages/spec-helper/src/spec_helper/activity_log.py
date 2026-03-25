"""Activity log section insertion for WP files."""

import re


def insert_activity_log_entry(body: str, entry: str) -> str:
    """Insert an activity log entry at the correct section boundary.

    Algorithm:
    1. Find ^## Activity Log (regex, first match)
    2. If found: find next ^## heading after it
       - If next heading found: insert entry on new line before that heading
       - If no next heading: append entry to end of file
    3. If not found: append ## Activity Log section + entry at EOF
    """
    activity_log_re = re.compile(r"^## Activity Log\s*$", re.MULTILINE)
    next_heading_re = re.compile(r"^## ", re.MULTILINE)

    match = activity_log_re.search(body)
    if match:
        search_start = match.end()
        next_heading = next_heading_re.search(body, search_start)
        if next_heading:
            insert_pos = next_heading.start()
            return body[:insert_pos].rstrip() + "\n" + entry + "\n\n" + body[insert_pos:]
        else:
            return body.rstrip() + "\n" + entry + "\n"
    else:
        return body.rstrip() + "\n\n## Activity Log\n\n" + entry + "\n"
