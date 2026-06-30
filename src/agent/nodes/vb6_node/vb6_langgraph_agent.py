import json
from vb6_tools import analyze_vb6_code_structure, is_vb6_binary
from vb6_prompts import VB6_TECH_PROMPT, VB6_HUMAN_PROMPT
from ds_llm import query_llm

# Load prompts
tech_prompt = VB6_TECH_PROMPT
human_prompt = VB6_HUMAN_PROMPT

# Process VB6 code by analyzing its structure and generating responses using DeepSeek LLM.
def process_vb6_code(vb6_code_path):
    """
    Process VB6 code by analyzing its structure and generating responses using DeepSeek LLM.

    Args:
        vb6_code_path (str): Path to the VB6 code file.

    Returns:
        dict: A dictionary containing the analysis result, technical response, and human response.
    """
    # Read VB6 code with error handling for encoding
    try:
        with open(vb6_code_path, "r", encoding="utf-8") as code_file:
            vb6_code = code_file.read()
    except UnicodeDecodeError:
        with open(vb6_code_path, "r", encoding="latin-1") as code_file:
            vb6_code = code_file.read()

    # Check if the file is a VB6 binary
    """try:
        if is_vb6_binary(vb6_code_path):
            raise ValueError("The provided file is a VB6 binary, not source code.")
    except Exception as e:
        raise ValueError(f"Error while checking binary content: {e}")
"""
    # Analyze VB6 code structure
    analysis_result = analyze_vb6_code_structure(vb6_code)

    # Generate technical response
    tech_response = query_llm(VB6_TECH_PROMPT, vb6_code)

    # Generate human-readable response
    human_response = query_llm(VB6_HUMAN_PROMPT, vb6_code)

    # Return the results
    return {
        "analysis": analysis_result,
        "technical_response": tech_response,
        "human_response": human_response,
    }

# Main function to analyze VB6 code and generate responses
def main():
    vb6_code_path = "C:\\Users\\Administrator\\Documents\\Stage\\Talan\\VB6\\Calculator\\frmCalculator.frm"  # Path to VB6 code file

    try:
        # Process the VB6 code
        results = process_vb6_code(vb6_code_path)

        # Save responses to JSON and TXT
        with open("../output_responses.json", "w", encoding="utf-8") as json_file:
            json.dump(results, json_file, indent=4)

        with open("../output_responses.txt", "w", encoding="utf-8") as txt_file:
            txt_file.write("Technical Response:\n")
            txt_file.write(results["technical_response"]["choices"][0]["message"]["content"] + "\n\n")
            txt_file.write("Human Response:\n")
            txt_file.write(results["human_response"]["choices"][0]["message"]["content"] + "\n")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
