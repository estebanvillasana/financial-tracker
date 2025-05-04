# Debug Guide for Financial Tracker

This guide explains how to use the debug configuration system in the Financial Tracker application.

## Overview

The Financial Tracker includes a debug configuration system that allows you to control which debug messages are displayed in the terminal. This is useful for troubleshooting specific parts of the application without cluttering the terminal with unrelated debug messages.

## Debug Categories

The following debug categories are available:

- **TABLE_DISPLAY**: Table contents display in the terminal
- **UNDERLYING_DATA**: Underlying data structures
- **DATE_ARROWS**: Date arrow rectangles positioning
- **ACCOUNT_CONVERSION**: Account ID conversion
- **SUBCATEGORY**: Subcategory handling
- **CURRENCY**: Currency formatting
- **DROPDOWN**: Dropdown selection
- **FOREIGN_KEYS**: Foreign key validation
- **CLICK_DETECTION**: Mouse click detection

## How to Access Debug Settings

There are two ways to access the debug settings:

1. **From the application menu**: Click on "Help" > "Debug Settings" in the application menu.

2. **From the command line**: Launch the application with the `--debug` flag:
   ```
   python expense_tracker_gui.py --debug
   ```

## Using the Debug Menu

The debug menu provides the following options:

1. **Toggle a debug category**: Enable or disable specific debug categories.
2. **Enable all categories**: Enable all debug categories at once.
3. **Disable all categories**: Disable all debug categories at once.
4. **Return to application**: Close the debug menu and return to the application.
5. **Exit program**: Save settings and exit the program completely.

Your debug settings are automatically saved when you make changes and will be remembered between program runs.

## Default Configuration

By default, the following debug categories are enabled:
- TABLE_DISPLAY
- UNDERLYING_DATA

All other categories are disabled by default.

## Tips for Debugging

- Enable only the categories you need to reduce clutter in the terminal.
- The TABLE_DISPLAY category shows the current state of the table as seen by the user.
- The UNDERLYING_DATA category shows the internal data structures that back the table.
- For UI-related issues, enable DATE_ARROWS and CLICK_DETECTION.
- For data-related issues, enable ACCOUNT_CONVERSION, SUBCATEGORY, and CURRENCY.

## Extending the Debug System

If you need to add new debug categories:

1. Add the new category to the `CATEGORIES` dictionary in `debug_config.py`.
2. Add the new category to the `enabled_categories` dictionary in `debug_config.py`.
3. Use `debug_print('YOUR_CATEGORY', 'Your message')` in your code.

## Troubleshooting

If you don't see any debug output:
- Make sure the relevant debug categories are enabled.
- Check that you're looking at the correct terminal window.
- Try enabling all categories to see if any debug output appears.
