#!/usr/bin/env python3
"""Remove duplicate methods from main_window.py that now exist in controllers."""

def remove_method_by_lines(filepath, method_name, start_line, end_line):
    """Remove a method from file by line range (1-indexed)."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Convert to 0-indexed
    start_idx = start_line - 1
    end_idx = end_line
    
    print(f"Removing {method_name} (lines {start_line}-{end_line}, {end_line - start_line + 1} lines)")
    print(f"  First line: {lines[start_idx].rstrip()}")
    print(f"  Last line: {lines[end_idx-1].rstrip()}")
    
    # Remove the lines
    new_lines = lines[:start_idx] + lines[end_idx:]
    
    with open(filepath, 'w') as f:
        f.writelines(new_lines)
    
    return len(new_lines)

def main():
    filepath = "gui/main_window.py"
    
    # Find exact line ranges for each duplicate method
    # These need to be determined by examining the file
    methods_to_remove = [
        # Format: (name, start, end)
        # Will find exact ranges by scanning
    ]
    
    # Read file and find method boundaries
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Find handle_chat_message
    for i, line in enumerate(lines, 1):
        if 'def handle_chat_message(self, message):' in line:
            print(f"Found handle_chat_message at line {i}")
            # Find next def at same indentation
            base_indent = len(line) - len(line.lstrip())
            for j in range(i, len(lines)):
                next_line = lines[j]
                if j > i and next_line.strip().startswith('def ') and (len(next_line) - len(next_line.lstrip())) == base_indent:
                    print(f"  Ends before line {j+1}")
                    methods_to_remove.append(('handle_chat_message', i, j))
                    break
    
    # Find on_chat_response
    for i, line in enumerate(lines, 1):
        if 'def on_chat_response(self, response):' in line:
            print(f"Found on_chat_response at line {i}")
            base_indent = len(line) - len(line.lstrip())
            for j in range(i, len(lines)):
                next_line = lines[j]
                if j > i and next_line.strip().startswith('def ') and (len(next_line) - len(next_line.lstrip())) == base_indent:
                    print(f"  Ends before line {j+1}")
                    methods_to_remove.append(('on_chat_response', i, j))
                    break
    
    # Find handle_continue
    for i, line in enumerate(lines, 1):
        if 'def handle_continue(self):' in line:
            print(f"Found handle_continue at line {i}")
            base_indent = len(line) - len(line.lstrip())
            for j in range(i, len(lines)):
                next_line = lines[j]
                if j > i and next_line.strip().startswith('def ') and (len(next_line) - len(next_line.lstrip())) == base_indent:
                    print(f"  Ends before line {j+1}")
                    methods_to_remove.append(('handle_continue', i, j))
                    break
    
    # Find handle_new_chat  
    for i, line in enumerate(lines, 1):
        if 'def handle_new_chat(self):' in line:
            print(f"Found handle_new_chat at line {i}")
            base_indent = len(line) - len(line.lstrip())
            for j in range(i, len(lines)):
                next_line = lines[j]
                if j > i and next_line.strip().startswith('def ') and (len(next_line) - len(next_line.lstrip())) == base_indent:
                    print(f"  Ends before line {j+1}")
                    methods_to_remove.append(('handle_new_chat', i, j))
                    break
    
    # Find handle_chat_link
    for i, line in enumerate(lines, 1):
        if 'def handle_chat_link(self, url):' in line:
            print(f"Found handle_chat_link at line {i}")
            base_indent = len(line) - len(line.lstrip())
            for j in range(i, len(lines)):
                next_line = lines[j]
                if j > i and next_line.strip().startswith('def ') and (len(next_line) - len(next_line.lstrip())) == base_indent:
                    print(f"  Ends before line {j+1}")
                    methods_to_remove.append(('handle_chat_link', i, j))
                    break
    
    print(f"\nTotal methods to remove: {len(methods_to_remove)}")
    print(f"Current file size: {len(lines)} lines")
    
    # Sort by line number descending to remove from bottom up
    methods_to_remove.sort(key=lambda x: x[1], reverse=True)
    
    # Remove each method
    for name, start, end in methods_to_remove:
        new_size = remove_method_by_lines(filepath, name, start, end)
        print(f"  New size: {new_size} lines")
    
    print(f"\nDone! Check git diff to verify removals.")

if __name__ == '__main__':
    main()
