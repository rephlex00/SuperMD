import re
from datetime import datetime


def expand_date_tokens(template_str: str, date_obj: datetime) -> str:
    """Replace {{DATE:<format>}} tokens with formatted date values."""
    def repl(match):
        return format_date(date_obj, match.group(1))
    return re.sub(r"\{\{DATE:(.+?)\}\}", repl, template_str)

def format_date(date_obj: datetime, format_str: str) -> str:
    """
    Format a datetime object using Obsidian-style tokens.
    
    Tokens supported:
    - YYYY: 4-digit year
    - YY: 2-digit year
    - MMMM: Full month name
    - MMM: Short month name
    - MM: 2-digit month
    - M: Month number
    - DD: 2-digit day
    - D: Day number
    - WW: ISO week number (01-53)
    - W: ISO week number (1-53)
    - dddd: Full day name
    - ddd: Short day name
    - d: Day of week (0-6, Sun-Sat or Mon-Sun depending on locale, here we use Python's)
    
    Text inside [] is escaped.
    """
    
    # 1. Handle escaped text: replace [...] with unique placeholders
    preserved = {}
    
    def repl_escape(match):
        # Use a placeholder that doesn't contain any date tokens (Y, M, D, W, d)
        # ESCAPED contains D. ESCAPE does not.
        key = f"__ESCAPE_{len(preserved)}__"
        preserved[key] = match.group(1)
        return key

    # simple regex to capture [text]
    # Note: nested brackets not supported
    processed_fmt = re.sub(r"\[(.*?)\]", repl_escape, format_str)
    
    # 2. Define replacements
    # Order matters: longer tokens first
    replacements = [
        ("YYYY", "%Y"),
        ("YY", "%y"),
        ("MMMM", "%B"),
        ("MMM", "%b"),
        ("MM", "%m"),
        ("M", "%-m"),  # Platform dependent, but usually works on Unix/Mac
        ("DD", "%d"),
        ("D", "%-d"),
        ("WW", "%V"), # ISO week number
        ("W", "%-V"), # ISO week number single digit if poss
        ("dddd", "%A"),
        ("ddd", "%a"),
        ("d", "%w"), # 0=Sunday, 6=Saturday
    ]
    
    # 3. Apply replacements
    # We must be careful not to replace characters that were just replaced.
    # Python's strftime handles standard % directives.
    # But wait, standard strftime doesn't support %-V or %-m on all platforms natively in pure python way without platform reliance?
    # Actually, let's just do manual string replacement using values from the date object
    # to avoid platform specific strftime issues and collisions.
    
    # Let's verify %-m support. Mac/Linux support it. Windows uses %#m. 
    # To be safe and cross-platform, let's just replace with the actual values.
    
    token_map = {
        "YYYY": str(date_obj.year),
        "YY": date_obj.strftime("%y"),
        "MMMM": date_obj.strftime("%B"),
        "MMM": date_obj.strftime("%b"),
        "MM": f"{date_obj.month:02d}",
        "M": str(date_obj.month),
        "DD": f"{date_obj.day:02d}",
        "D": str(date_obj.day),
        "WW": f"{date_obj.isocalendar()[1]:02d}", 
        "W": str(date_obj.isocalendar()[1]),
        "dddd": date_obj.strftime("%A"),
        "ddd": date_obj.strftime("%a"),
        "d": date_obj.strftime("%w"),
    }
    
    # We need to iterate through the string and replace tokens.
    # Since tokens can share characters (e.g. MMMM vs MM), we should consume the string.
    # A regex pattern is best.
    
    pattern = "|".join(re.escape(k) for k, _ in replacements) # Use the list to maintain order
    
    def repl_token(match):
        token = match.group(0)
        return token_map.get(token, token)
        
    final_str = re.sub(pattern, repl_token, processed_fmt)
    
    # 4. Restore escaped text
    for key, value in preserved.items():
        final_str = final_str.replace(key, value)
        
    return final_str
