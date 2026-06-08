"""
CRM Chatbot — entry point.
Run: python main.py
"""
import sys
import os

# Add project root to Python path so `src.*` imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.chatbot.cli import main

if __name__ == "__main__":
    main()
