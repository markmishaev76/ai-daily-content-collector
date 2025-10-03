"""
Test Email Scanning Feature
Scans your email for tech content and shows what it finds
"""

import sys
import os
from dotenv import load_dotenv
from src.email_scanner import EmailScanner

def test_email_scanning():
    """Test the email scanning functionality"""
    print("=" * 60)
    print("Testing Email Scanning for Tech Content")
    print("=" * 60)
    print()
    
    # Load environment variables
    load_dotenv()
    
    try:
        # Initialize email scanner
        scanner = EmailScanner()
        
        print("🔍 Scanning your email for tech content...")
        print("Looking for emails from the last 7 days...")
        print()
        
        # Scan emails
        articles = scanner.scan_emails_for_content(days_back=7)
        
        if articles:
            print(f"✅ Found {len(articles)} tech-related articles in your email!")
            print()
            
            print("📧 Articles found:")
            print("-" * 40)
            
            for i, article in enumerate(articles[:10], 1):  # Show first 10
                print(f"{i}. {article['title']}")
                print(f"   From: {article['source']}")
                if article['link']:
                    print(f"   Link: {article['link']}")
                if article['summary']:
                    print(f"   Summary: {article['summary'][:100]}...")
                print()
            
            if len(articles) > 10:
                print(f"... and {len(articles) - 10} more articles")
            
            print("=" * 60)
            print("✅ Email scanning is working! These articles will be included in your daily brief.")
            
        else:
            print("⚠️  No tech-related articles found in your email.")
            print()
            print("This could mean:")
            print("- No tech newsletters in your inbox")
            print("- Tech emails are in a different folder")
            print("- Email scanning needs adjustment")
            print()
            print("💡 Try subscribing to some tech newsletters to test the feature!")
        
        return len(articles) > 0
        
    except Exception as e:
        print(f"❌ Error during email scanning: {str(e)}")
        print()
        print("Common issues:")
        print("- Check your email credentials in .env")
        print("- Ensure IMAP is enabled in Gmail")
        print("- Verify your app password is correct")
        return False

if __name__ == "__main__":
    success = test_email_scanning()
    sys.exit(0 if success else 1)

