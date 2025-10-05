"""
Test script to generate a brief immediately
Useful for testing your configuration before scheduling
"""

import sys
from main import generate_brief

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Personal AI Assistant - Brief Generation")
    print("=" * 60)
    print()
    
    success = generate_brief()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Test completed successfully! Check your email.")
    else:
        print("❌ Test failed. Check the logs above for errors.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)





