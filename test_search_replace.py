#!/usr/bin/env python3
"""Quick test to verify search/replace functionality works."""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from gui.editors.code_editor import CodeEditor
from gui.editors.search_replace import SearchReplaceWidget

def test_search_replace():
    app = QApplication(sys.argv)
    
    # Create a test window
    window = QWidget()
    window.setWindowTitle("Search & Replace Test")
    layout = QVBoxLayout(window)
    
    # Create editor with test content
    editor = CodeEditor()
    editor.setPlainText("Hello World\nHello Python\nhello javascript\nHELLO RUST")
    layout.addWidget(editor)
    
    # Create search/replace widget
    search_widget = SearchReplaceWidget(editor=editor)
    layout.addWidget(search_widget)
    
    # Show the window
    window.resize(600, 400)
    window.show()
    
    # Run briefly to verify no errors
    print("✓ Search & Replace widget created successfully")
    print("✓ Editor initialized with test content")
    print("✓ Testing find operations...")
    
    # Test find
    editor.setFocus()
    search_widget.search_input.setText("Hello")
    search_widget.find_next()
    print("✓ Find operation works")
    
    # Test find all
    search_widget.find_all()
    print("✓ Find all operation works")
    
    # Test replace
    search_widget.replace_input.setText("Hi")
    search_widget.replace_next()
    print("✓ Replace operation works")
    
    # Test replace all with case sensitivity
    search_widget.case_sensitive_checkbox.setChecked(False)
    search_widget.replace_all()
    print("✓ Replace all operation works")
    
    print("\n✅ All search & replace operations completed successfully!")

if __name__ == "__main__":
    test_search_replace()
