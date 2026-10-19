#!/usr/bin/env python3
"""
API Key Validation & Setup Helper
===============================
Quick script to test and validate the Gemini API key setup
"""

import os
import sys
from pathlib import Path

def check_api_key():
    """Check if API key is properly configured"""
    print("🔑 GEMINI API KEY VALIDATION")
    print("=" * 40)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ No API key found!")
        print("\n💡 To set up your API key:")
        print("1. Get an API key from: https://makersuite.google.com/app/apikey")
        print("2. Set environment variable in PowerShell:")
        print('   $env:GEMINI_API_KEY = "your-actual-api-key-here"')
        print("3. Restart your terminal and try again")
        return False
    
    if api_key == "your-api-key-here" or api_key == "GEMINI_API_KEY_HERE":
        print("❌ Placeholder API key detected!")
        print(f"Current key: {api_key}")
        print("\n💡 Please replace with your actual Google Gemini API key")
        return False
    
    # Basic validation
    if len(api_key) < 20:
        print("⚠️  API key seems too short")
        print(f"Length: {len(api_key)} characters")
        return False
    
    print("✅ API key is configured!")
    print(f"📊 Key length: {len(api_key)} characters")
    print(f"🔒 Key preview: {api_key[:8]}...{api_key[-8:]}")
    
    return True

def test_api_connection():
    """Test basic API connection"""
    try:
        # Add generic node to path
        current_dir = Path(__file__).parent
        generic_node_dir = current_dir.parent / "generic_node_with_api"
        sys.path.insert(0, str(generic_node_dir))
        
        from generic_node import GenericCodeAnalysisNodeLangChain
        
        print("\n🧪 TESTING API CONNECTION")
        print("-" * 30)
        
        # Create a small test file
        test_content = '''def hello_world():
    """Simple test function"""
    return "Hello, World!"
'''
        
        test_file = current_dir / "api_test.py"
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        try:
            # Test the API
            node = GenericCodeAnalysisNodeLangChain()
            result = node.analyze_file({
                "file_path": str(test_file),
                "language": "python"
            })
            
            if result.get('status') == 'analyzed':
                print("✅ API connection successful!")
                print("🎉 Your setup is working correctly!")
                success = True
            else:
                print(f"❌ API test failed: {result.get('message', 'Unknown error')}")
                success = False
                
        finally:
            # Clean up test file
            if test_file.exists():
                test_file.unlink()
        
        return success
        
    except ImportError as e:
        print(f"❌ Could not import generic node: {e}")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def main():
    """Main validation function"""
    print("🛠️  E-COMMERCE PIPELINE SETUP VALIDATOR")
    print("=" * 50)
    
    # Check API key
    if not check_api_key():
        print("\n🔧 Please fix the API key setup and try again.")
        return
    
    # Test API connection
    if test_api_connection():
        print("\n🚀 READY TO RUN E-COMMERCE PIPELINE!")
        print("-" * 40)
        print("Your setup is complete. You can now run:")
        print("  python ecommerce_pipeline.py")
    else:
        print("\n🔧 API connection failed. Please check:")
        print("1. API key is valid and active")
        print("2. Internet connection is working")
        print("3. Google Gemini API service is available")

if __name__ == "__main__":
    main()
