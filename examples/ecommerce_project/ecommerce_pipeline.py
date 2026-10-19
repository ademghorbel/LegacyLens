#!/usr/bin/env python3
"""
E-Commerce Application Analysis Pipeline
=====================================
Complete test pipeline for Generic Node → Module Aggregation → RFP Generation

This script:
1. Analyzes the comprehensive e-commerce application files
2. Exports individual analysis results to analysis_outputs/
3. Aggregates results into RFP format in aggregation_results/
4. Validates the complete pipeline functionality
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

def setup_paths():
    """Setup all necessary paths for the pipeline"""
    current_dir = Path(__file__).parent
    
    paths = {
        'current_dir': current_dir,
        'generic_node_dir': current_dir.parent / "generic_node_with_api",
        'aggregation_node_dir': current_dir.parent / "module_aggregation_node", 
        'analysis_outputs_dir': current_dir.parent.parent.parent / "analysis_outputs",
        'aggregation_results_dir': current_dir.parent.parent.parent / "aggregation_results"
    }
    
    # Ensure aggregation results directory exists
    paths['aggregation_results_dir'].mkdir(exist_ok=True)
    
    return paths

def import_analysis_modules(paths):
    """Import the required analysis modules"""
    try:
        # Add generic node to path
        sys.path.insert(0, str(paths['generic_node_dir']))
        from generic_node import analyze_code_file
        
        # Add aggregation node to path  
        sys.path.insert(0, str(paths['aggregation_node_dir']))
        from module_aggregation_node import aggregate_analysis_results
        
        return analyze_code_file, aggregate_analysis_results
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        return None, None

def get_test_files():
    """Get list of files to analyze in the e-commerce application"""
    return [
        ("auth_service.py", "python", "Authentication Service"),
        ("product_service.py", "python", "Product Management Service"),
        ("order_service.py", "python", "Order Processing Service"),
        ("notification_service.py", "python", "Notification Service"),
        ("database_config.py", "python", "Database Configuration"),
        ("Dashboard.tsx", "typescript", "React Admin Dashboard"),
        ("package.json", "json", "Frontend Dependencies"),
        ("requirements.txt", "text", "Backend Dependencies")
    ]

def run_generic_node_analysis(analyze_code_file, paths):
    """Run Generic Node analysis on all test files"""
    print("🔬 STEP 1: GENERIC NODE ANALYSIS")
    print("-" * 50)
    
    test_files = get_test_files()
    successful_analyses = []
    failed_analyses = []
    
    for i, (filename, language, description) in enumerate(test_files, 1):
        file_path = paths['current_dir'] / filename
        
        if not file_path.exists():
            print(f"⚠️  File {i}/{len(test_files)}: {filename} - SKIPPED (not found)")
            failed_analyses.append((filename, "File not found"))
            continue
        
        print(f"🔍 File {i}/{len(test_files)}: {description}")
        print(f"   📁 {filename} ({language})")
        
        try:
            result = analyze_code_file(str(file_path), language)
            
            if result.get('status') == 'analyzed':
                print(f"   ✅ SUCCESS - Analysis completed")
                successful_analyses.append((filename, result))
                
                # Show brief summary
                analysis = result.get('analysis', {})
                if isinstance(analysis, dict):
                    if 'file_summary' in analysis:
                        file_summary = analysis['file_summary']
                        role = file_summary.get('role', 'Unknown')
                        purpose = file_summary.get('purpose', 'Not specified')[:60]
                        print(f"   📝 Role: {role}")
                        print(f"   🎯 Purpose: {purpose}...")
                    elif 'modules' in analysis and isinstance(analysis['modules'], list):
                        print(f"   📦 Extracted {len(analysis['modules'])} modules")
                
            else:
                error_msg = result.get('message', 'Unknown error')
                print(f"   ❌ FAILED - {error_msg}")
                failed_analyses.append((filename, error_msg))
                
        except Exception as e:
            print(f"   ❌ ERROR - {str(e)}")
            failed_analyses.append((filename, str(e)))
        
        print()
        time.sleep(0.5)  # Brief pause between analyses
    
    print(f"📊 GENERIC NODE ANALYSIS SUMMARY")
    print(f"   ✅ Successful: {len(successful_analyses)}/{len(test_files)}")
    print(f"   ❌ Failed: {len(failed_analyses)}/{len(test_files)}")
    
    if failed_analyses:
        print(f"\n⚠️  Failed Files:")
        for filename, error in failed_analyses:
            print(f"   • {filename}: {error}")
    
    return successful_analyses, failed_analyses

def run_module_aggregation(aggregate_analysis_results, paths, successful_analyses):
    """Run Module Aggregation on the analysis results"""
    print(f"\n🔗 STEP 2: MODULE AGGREGATION")
    print("-" * 50)
    
    if len(successful_analyses) == 0:
        print("❌ No successful analyses to aggregate")
        return None
    
    try:
        print(f"🤖 Running Module Aggregation Node...")
        print(f"   📊 Processing {len(successful_analyses)} analysis results...")
        
        aggregation_result = aggregate_analysis_results()
        
        if aggregation_result.get('status') == 'aggregated':
            modules = aggregation_result.get('modules', [])
            print(f"   ✅ SUCCESS - Created {len(modules)} modules")
            
            # Copy aggregation result to our dedicated folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            aggregation_file = paths['aggregation_results_dir'] / f"ecommerce_rfp_modules_{timestamp}.json"
            
            with open(aggregation_file, 'w', encoding='utf-8') as f:
                json.dump(aggregation_result, f, indent=2, ensure_ascii=False)
            
            print(f"   📄 RFP JSON saved: {aggregation_file.name}")
            
            # Display module summary
            print(f"\n📦 EXTRACTED MODULES:")
            for i, module in enumerate(modules, 1):
                name = module.get('module_name', 'Unknown')
                description = module.get('module_description', 'No description')
                tech_stack = module.get('tech_stack', [])
                endpoints = module.get('endpoints', [])
                entities = module.get('entities', {})
                
                print(f"   {i}. {name}")
                print(f"      📝 {description[:70]}...")
                print(f"      🔧 Tech: {', '.join(tech_stack[:3])}")
                print(f"      🌐 Endpoints: {len(endpoints)}")
                print(f"      🗃️  Entities: {len(entities)}")
                print()
            
            return aggregation_result
            
        else:
            error_msg = aggregation_result.get('message', 'Unknown error')
            print(f"   ❌ FAILED - {error_msg}")
            return None
            
    except Exception as e:
        print(f"   ❌ ERROR - {str(e)}")
        return None

def display_pipeline_summary(paths, successful_analyses, aggregation_result):
    """Display final pipeline summary"""
    print(f"\n🎯 E-COMMERCE PIPELINE TEST SUMMARY")
    print("=" * 60)
    
    # Generic Node Results
    total_files = len(get_test_files())
    success_rate = (len(successful_analyses) / total_files * 100) if total_files > 0 else 0
    print(f"🔬 Generic Node Analysis:")
    print(f"   ✅ Files processed: {len(successful_analyses)}/{total_files}")
    print(f"   📈 Success rate: {success_rate:.1f}%")
    
    # Module Aggregation Results
    if aggregation_result:
        modules_count = len(aggregation_result.get('modules', []))
        print(f"🔗 Module Aggregation:")
        print(f"   ✅ Modules created: {modules_count}")
        print(f"   🚀 RFP format: Ready for code generation!")
    else:
        print(f"🔗 Module Aggregation:")
        print(f"   ❌ Failed or skipped")
    
    # Output Files
    print(f"\n📂 Output Locations:")
    print(f"   📊 Individual analyses: {paths['analysis_outputs_dir']}/")
    print(f"   📋 Aggregated modules: {paths['aggregation_results_dir']}/")
    
    # Check if files exist
    if paths['analysis_outputs_dir'].exists():
        json_files = list(paths['analysis_outputs_dir'].glob("*.json"))
        print(f"   📄 Analysis files: {len(json_files)} JSON files")
    
    if paths['aggregation_results_dir'].exists():
        rfp_files = list(paths['aggregation_results_dir'].glob("*.json"))
        print(f"   📄 RFP files: {len(rfp_files)} JSON files")
    
    # Next Steps
    print(f"\n🎯 NEXT STEPS:")
    if len(successful_analyses) > 0:
        print(f"   1. ✅ Review individual analysis files")
        if aggregation_result:
            print(f"   2. ✅ Check the aggregated RFP modules")
            print(f"   3. 🚀 Use RFP output for code generation")
            print(f"   4. 📋 Validate module extraction accuracy")
        else:
            print(f"   2. 🔧 Fix aggregation issues and retry")
    else:
        print(f"   1. 🔧 Fix API key or analysis issues")
        print(f"   2. 🔄 Re-run the pipeline")
    
    # Success indicator
    if len(successful_analyses) > 0 and aggregation_result:
        print(f"\n🎉 PIPELINE COMPLETED SUCCESSFULLY!")
        print(f"🏆 Your e-commerce application analysis is ready!")
    elif len(successful_analyses) > 0:
        print(f"\n⚠️  PIPELINE PARTIALLY COMPLETED")
        print(f"🔧 Analysis successful, but aggregation needs attention")
    else:
        print(f"\n❌ PIPELINE FAILED")
        print(f"🔧 Check API configuration and try again")

def main():
    """Main pipeline execution"""
    print("🚀 E-COMMERCE APPLICATION ANALYSIS PIPELINE")
    print("=" * 60)
    print("🎯 Testing: Generic Node → Module Aggregation → RFP Generation")
    print()
    
    # Setup
    print("⚙️  Setting up analysis environment...")
    paths = setup_paths()
    
    print(f"📁 Working directory: {paths['current_dir']}")
    print(f"🔧 Generic Node: {paths['generic_node_dir']}")
    print(f"🔗 Aggregation Node: {paths['aggregation_node_dir']}")
    print(f"📊 Analysis outputs: {paths['analysis_outputs_dir']}")
    print(f"📋 Aggregation results: {paths['aggregation_results_dir']}")
    print()
    
    # Import modules
    analyze_code_file, aggregate_analysis_results = import_analysis_modules(paths)
    if not analyze_code_file or not aggregate_analysis_results:
        print("❌ Failed to setup required modules. Exiting.")
        return
    
    print("✅ Analysis modules imported successfully")
    print()
    
    # Run analysis pipeline
    successful_analyses, failed_analyses = run_generic_node_analysis(analyze_code_file, paths)
    
    aggregation_result = None
    if successful_analyses:
        aggregation_result = run_module_aggregation(aggregate_analysis_results, paths, successful_analyses)
    
    # Display summary
    display_pipeline_summary(paths, successful_analyses, aggregation_result)

if __name__ == "__main__":
    main()
