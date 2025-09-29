#!/usr/bin/env python3
"""
DocBrains Backend API Testing Suite
Tests all API endpoints for the document processing application
"""

import requests
import sys
import json
import time
import tempfile
import os
from datetime import datetime
from pathlib import Path

class DocBrainsAPITester:
    def __init__(self, base_url="https://docbrains.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.uploaded_document_id = None

    def log_test(self, name, success, details="", error_msg=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {error_msg}")
        
        self.test_results.append({
            "test_name": name,
            "success": success,
            "details": details,
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        })

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            success = response.status_code == 200
            details = response.json() if success else f"Status: {response.status_code}"
            self.log_test("API Root", success, details, "" if success else f"Expected 200, got {response.status_code}")
            return success
        except Exception as e:
            self.log_test("API Root", False, "", str(e))
            return False

    def test_get_documents_empty(self):
        """Test getting documents when none exist"""
        try:
            response = requests.get(f"{self.api_url}/documents", timeout=10)
            success = response.status_code == 200
            if success:
                data = response.json()
                details = f"Found {len(data)} documents"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("Get Documents (Empty)", success, details, "" if success else f"Expected 200, got {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Get Documents (Empty)", False, "", str(e))
            return False

    def create_test_pdf(self):
        """Create a simple test PDF file"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            c = canvas.Canvas(temp_file.name, pagesize=letter)
            
            # Add multiple pages with content
            for page_num in range(1, 4):  # 3 pages
                c.drawString(100, 750, f"DocBrains Test Document - Page {page_num}")
                c.drawString(100, 700, f"This is test content for page {page_num}.")
                c.drawString(100, 650, "This document tests the PDF processing capabilities.")
                c.drawString(100, 600, f"Important information on page {page_num}: Lorem ipsum dolor sit amet.")
                c.drawString(100, 550, "The AI should extract all content from all pages without omitting anything.")
                c.drawString(100, 500, f"Page {page_num} contains critical data that must be preserved.")
                c.showPage()
            
            c.save()
            temp_file.close()
            return temp_file.name
        except Exception as e:
            print(f"Error creating test PDF: {e}")
            return None

    def test_file_upload(self):
        """Test file upload functionality"""
        pdf_path = self.create_test_pdf()
        if not pdf_path:
            self.log_test("File Upload", False, "", "Could not create test PDF")
            return False

        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': ('test_document.pdf', f, 'application/pdf')}
                response = requests.post(f"{self.api_url}/upload", files=files, timeout=60)
            
            success = response.status_code == 200
            if success:
                data = response.json()
                self.uploaded_document_id = data.get('id')
                details = f"Document ID: {self.uploaded_document_id}, Text length: {data.get('text_length', 0)}"
                
                # Verify text extraction worked
                if data.get('text_length', 0) < 50:
                    success = False
                    error_msg = f"Text extraction failed - only {data.get('text_length', 0)} characters extracted"
                else:
                    error_msg = ""
            else:
                details = f"Status: {response.status_code}"
                error_msg = response.text if response.text else f"Expected 200, got {response.status_code}"
            
            self.log_test("File Upload", success, details, error_msg)
            
            # Cleanup
            os.unlink(pdf_path)
            return success
            
        except Exception as e:
            self.log_test("File Upload", False, "", str(e))
            if pdf_path and os.path.exists(pdf_path):
                os.unlink(pdf_path)
            return False

    def test_get_document_details(self):
        """Test getting specific document details"""
        if not self.uploaded_document_id:
            self.log_test("Get Document Details", False, "", "No document ID available")
            return False

        try:
            response = requests.get(f"{self.api_url}/document/{self.uploaded_document_id}", timeout=10)
            success = response.status_code == 200
            if success:
                data = response.json()
                details = f"Filename: {data.get('filename')}, Text length: {len(data.get('extracted_text', ''))}"
                
                # Verify all required fields are present
                required_fields = ['id', 'filename', 'content_type', 'file_size', 'extracted_text']
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    success = False
                    error_msg = f"Missing fields: {missing_fields}"
                else:
                    error_msg = ""
            else:
                details = f"Status: {response.status_code}"
                error_msg = f"Expected 200, got {response.status_code}"
            
            self.log_test("Get Document Details", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("Get Document Details", False, "", str(e))
            return False

    def test_generate_summary(self):
        """Test summary generation"""
        if not self.uploaded_document_id:
            self.log_test("Generate Summary", False, "", "No document ID available")
            return False

        try:
            payload = {
                "document_id": self.uploaded_document_id,
                "summary_type": "medio",
                "accuracy_level": "alta"
            }
            response = requests.post(f"{self.api_url}/generate-summary", json=payload, timeout=120)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                summary_length = len(data.get('summary', ''))
                details = f"Summary generated, length: {summary_length} characters"
                
                # Verify summary is reasonable length
                if summary_length < 100:
                    success = False
                    error_msg = f"Summary too short: {summary_length} characters"
                else:
                    error_msg = ""
            else:
                details = f"Status: {response.status_code}"
                error_msg = response.text if response.text else f"Expected 200, got {response.status_code}"
            
            self.log_test("Generate Summary", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("Generate Summary", False, "", str(e))
            return False

    def test_generate_schema(self):
        """Test schema generation"""
        if not self.uploaded_document_id:
            self.log_test("Generate Schema", False, "", "No document ID available")
            return False

        try:
            payload = {
                "document_id": self.uploaded_document_id,
                "schema_type": "brainstorming"
            }
            response = requests.post(f"{self.api_url}/generate-schema", json=payload, timeout=120)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                schema_length = len(data.get('schema', ''))
                details = f"Schema generated, length: {schema_length} characters"
                
                # Verify schema is reasonable length
                if schema_length < 50:
                    success = False
                    error_msg = f"Schema too short: {schema_length} characters"
                else:
                    error_msg = ""
            else:
                details = f"Status: {response.status_code}"
                error_msg = response.text if response.text else f"Expected 200, got {response.status_code}"
            
            self.log_test("Generate Schema", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("Generate Schema", False, "", str(e))
            return False

    def test_chat_functionality(self):
        """Test AI chat functionality"""
        if not self.uploaded_document_id:
            self.log_test("Chat Functionality", False, "", "No document ID available")
            return False

        try:
            payload = {
                "document_id": self.uploaded_document_id,
                "message": "Puoi riassumere brevemente il contenuto di questo documento?",
                "context": "Test document context"
            }
            response = requests.post(f"{self.api_url}/chat", json=payload, timeout=60)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                response_length = len(data.get('response', ''))
                details = f"Chat response length: {response_length} characters"
                
                # Verify response is reasonable
                if response_length < 20:
                    success = False
                    error_msg = f"Chat response too short: {response_length} characters"
                else:
                    error_msg = ""
            else:
                details = f"Status: {response.status_code}"
                error_msg = response.text if response.text else f"Expected 200, got {response.status_code}"
            
            self.log_test("Chat Functionality", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("Chat Functionality", False, "", str(e))
            return False

    def test_export_pdf(self):
        """Test PDF export functionality"""
        if not self.uploaded_document_id:
            self.log_test("Export PDF", False, "", "No document ID available")
            return False

        try:
            # Test exporting full text
            response = requests.get(f"{self.api_url}/export-pdf/{self.uploaded_document_id}?content_type=full", timeout=30)
            success = response.status_code == 200
            
            if success:
                content_length = len(response.content)
                details = f"PDF exported, size: {content_length} bytes"
                
                # Verify PDF content
                if content_length < 1000:  # PDF should be at least 1KB
                    success = False
                    error_msg = f"PDF too small: {content_length} bytes"
                elif not response.content.startswith(b'%PDF'):
                    success = False
                    error_msg = "Response is not a valid PDF"
                else:
                    error_msg = ""
            else:
                details = f"Status: {response.status_code}"
                error_msg = response.text if response.text else f"Expected 200, got {response.status_code}"
            
            self.log_test("Export PDF", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("Export PDF", False, "", str(e))
            return False

    def test_file_size_limit(self):
        """Test file size limit enforcement"""
        try:
            # Create a large dummy file (simulate >100MB)
            large_content = b'0' * (101 * 1024 * 1024)  # 101MB
            
            files = {'file': ('large_file.pdf', large_content, 'application/pdf')}
            response = requests.post(f"{self.api_url}/upload", files=files, timeout=30)
            
            # Should return 413 (Payload Too Large) or 400 (Bad Request)
            success = response.status_code in [413, 400]
            details = f"Status: {response.status_code}"
            error_msg = "" if success else f"Expected 413 or 400, got {response.status_code}"
            
            self.log_test("File Size Limit", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("File Size Limit", False, "", str(e))
            return False

    def test_invalid_file_type(self):
        """Test invalid file type rejection"""
        try:
            # Create a text file (should be rejected)
            text_content = b'This is a text file, not a PDF or image'
            
            files = {'file': ('test.txt', text_content, 'text/plain')}
            response = requests.post(f"{self.api_url}/upload", files=files, timeout=10)
            
            # Should return 400 (Bad Request)
            success = response.status_code == 400
            details = f"Status: {response.status_code}"
            error_msg = "" if success else f"Expected 400, got {response.status_code}"
            
            self.log_test("Invalid File Type", success, details, error_msg)
            return success
        except Exception as e:
            self.log_test("Invalid File Type", False, "", str(e))
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting DocBrains Backend API Tests")
        print(f"📍 Testing API at: {self.api_url}")
        print("=" * 60)
        
        # Basic connectivity tests
        self.test_api_root()
        self.test_get_documents_empty()
        
        # File upload and processing tests
        self.test_file_upload()
        self.test_get_document_details()
        
        # AI processing tests (only if upload succeeded)
        if self.uploaded_document_id:
            print("\n🤖 Testing AI Processing Features...")
            self.test_generate_summary()
            time.sleep(2)  # Brief pause between AI calls
            self.test_generate_schema()
            time.sleep(2)
            self.test_chat_functionality()
            self.test_export_pdf()
        
        # Error handling tests
        print("\n🛡️ Testing Error Handling...")
        self.test_file_size_limit()
        self.test_invalid_file_type()
        
        # Print final results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("❌ Some tests failed. Check the details above.")
            return 1

    def get_test_summary(self):
        """Get a summary of test results"""
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": self.tests_run - self.tests_passed,
            "success_rate": (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0,
            "test_details": self.test_results,
            "uploaded_document_id": self.uploaded_document_id
        }

def main():
    """Main test execution"""
    tester = DocBrainsAPITester()
    exit_code = tester.run_all_tests()
    
    # Save detailed results
    results = tester.get_test_summary()
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())