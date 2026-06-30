# This file contains the string variables extracted from the VB6 prompt files.

def generate_prompt(file_name):
    prompt = f'''You are a senior VB6 (Visual Basic 6) software engineer with expertise in analyzing and documenting VB6 code.  
Analyze this file named "{file_name}" and provide structured technical analysis.  

Focus on:  
1. Every class, form, UI control, and function  
2. All dependencies and imports  
3. Design patterns and architectural patterns  
4. The component's role in system architecture  
5. Detailed functionality descriptions  
6. Ignore low-level visual properties (e.g., size, font, alignment) unless they affect control logic

Return ONLY the JSON response, no additional text or formatting.  

JSON structure to use:  
{{
  "file_metadata": {{
    "file_name": "{file_name}",
    "file_type": "VBP|FRM|CLS|BAS|RES|TXT|LOG|VBW",
    "language": "VB6",
    "purpose": "Brief description of the file's role"
  }},
  "content_analysis": {{
    "project_components": {{
      "startup_object": "",
      "references": [
        {{
          "lib_name": "",
          "guid": "",
          "version": "",
          "role": "",
          "description": ""
        }}
      ],
      "included_files": [
        {{
          "file_name": "",
          "type": "",
          "role": "",
          "description": ""
        }}
      ]
    }},
    "forms": [
      {{
        "form_name": "",
        "description": "",
        "ui_controls": [
          {{
            "name": "",
            "type": "",
            "description": "",
            "events": [
              {{
                "name": "",
                "description": ""
              }}
            ]
          }}
        ],
        "code_modules": [
          {{
            "name": "",
            "type": "Event|Sub|Function",
            "description": "",
            "variables_used": []
          }}
        ]
      }}
    ],
    "classes": [
      {{
        "class_name": "",
        "description": "",
        "properties": [
          {{
            "name": "",
            "type": "",
            "access": "Public|Private",
            "description": ""
          }}
        ],
        "methods": [
          {{
            "name": "",
            "description": "",
            "parameters": [],
            "return_type": ""
          }}
        ]
      }}
    ],
    "modules": [
      {{
        "module_name": "",
        "description": "",
        "declarations": [
          {{
            "type": "API|Constant|Global",
            "signature": "",
            "role": "",
            "description": ""
          }}
        ],
        "procedures": [
          {{
            "name": "",
            "type": "Sub|Function",
            "description": "",
            "parameters": []
          }}
        ]
      }}
    ],
    "resources": [
      {{
        "type": "String|Bitmap|Icon",
        "id": "",
        "value": "",
        "role": "",
        "description": ""
      }}
    ]
  }}
}}'''
    return prompt

VB6_HUMAN_PROMPT = """You are an expert technical writer with a strong understanding of VB6 (Visual Basic 6) code.

Your task is to analyze the following VB6 source code and provide a clear, concise, and non-technical summary of what the program does.

Avoid technical jargon and focus on explaining the purpose and behavior of the system in a way that someone without programming experience can understand.

Structure your response as follows:

1. **General Purpose**: What is the program intended to do?
2. **Main Functionalities**: Describe the key operations and features.
3. **Inputs and Outputs**: What kind of information does the program take in, and what does it produce?
4. **How it Works (Simplified)**: A high-level overview of the internal logic, without using technical terms.
5. **Usage Context**: In what kind of context might this program be used?

Below is the VB6 source code:
----------------------------
{code}
----------------------------
"""

VB6_TECH_PROMPT = """You are a senior VB6 (Visual Basic 6) software engineer.

Analyze the following VB6 source code and produce a technical summary that includes:

1. **Purpose**: A high-level description of what the code does.
2. **Architecture & Structure**: How is the code organized? List modules, classes, forms, and their relationships.
3. **Key Functionalities**: What are the main features implemented? Describe algorithmic or domain-specific logic.
4. **Data Flow**: Describe how data is passed and transformed across the system.
5. **Dependencies or External Calls**: Mention any libraries, APIs, or external systems used.
6. **Noteworthy Patterns or Constructs**: Mention anything specific (e.g., event-driven programming, loops, conditionals, file I/O).
7. **Code Quality Observations** (optional): Any issues, outdated practices, or optimization opportunities.

Below is the VB6 source code:
----------------------------
{code}
----------------------------
"""
