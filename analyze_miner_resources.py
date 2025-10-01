#!/usr/bin/env python3
"""
Polaris Validator - Miner Resource Analysis Script

This script queries all miners and provides detailed statistics about their
CPU and GPU resources, including compute scores and resource distribution.

Usage:
    python analyze_miner_resources.py [--detailed] [--export-csv] [--filter-gpu] [--filter-cpu]
"""

import requests
import json
import sys
import argparse
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime
import re

# API Configuration
API_URL = "https://polariscloudai-main-pf5lil.laravel.cloud/api/v1/validator/miners"
API_HEADERS = {
    "Connection": "keep-alive",
    "x-api-key": "",
    "service-key": "",
    "service-name": "miner_service",
    "Content-Type": "application/json"
}

# Import compute score calculation from the actual validator code
sys.path.insert(0, '/Users/user/Documents/Jarvis/polarisvalidator/neurons')
try:
    from utils.compute_score import calculate_compute_score
    from utils.gpu_specs import get_gpu_weight
    COMPUTE_SCORE_AVAILABLE = True
except ImportError:
    print("⚠️  Warning: Could not import compute_score module. Score calculations will be disabled.")
    COMPUTE_SCORE_AVAILABLE = False


class MinerResourceAnalyzer:
    """Analyzes miner resources and provides detailed statistics."""
    
    def __init__(self):
        self.miners_data = []
        self.stats = {
            'total_miners': 0,
            'miners_with_resources': 0,
            'miners_registered': 0,
            'total_resources': 0,
            'cpu_only_resources': 0,
            'gpu_resources': 0,
            'gpu_types': defaultdict(int),
            'cpu_cores_distribution': [],
            'gpu_memory_distribution': [],
            'compute_scores': [],
            'miners_by_uid': {},
            'verification_status': defaultdict(int)
        }
    
    def fetch_miners(self) -> bool:
        """Fetch miner data from the API."""
        try:
            print("🔄 Fetching miners data from API...")
            response = requests.get(API_URL, headers=API_HEADERS, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.miners_data = data.get("miners", [])
            
            print(f"✅ Successfully fetched {len(self.miners_data)} miners")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching miners data: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON response: {e}")
            return False
    
    def parse_cpu_specs(self, specs: Dict[str, Any]) -> Dict[str, Any]:
        """Parse CPU specifications from resource specs."""
        cpu_info = {
            "model": specs.get("cpu_model", "Unknown"),
            "cores": specs.get("cpu_cores", 0),
            "speed_mhz": specs.get("cpu_speed_mhz", 0),
            "threads_per_core": specs.get("threads_per_core", 1),
            "total_threads": 0
        }
        
        # Calculate total threads
        if cpu_info["cores"] > 0 and cpu_info["threads_per_core"] > 0:
            cpu_info["total_threads"] = cpu_info["cores"] * cpu_info["threads_per_core"]
        
        # Try to extract from system_info if missing
        if cpu_info["model"] == "Unknown":
            system_info = specs.get("system_info", "")
            if system_info:
                cpu_info["model"] = system_info.split()[-1] if system_info.split() else "Unknown"
        
        return cpu_info
    
    def parse_gpu_specs(self, specs: Dict[str, Any]) -> Dict[str, Any]:
        """Parse GPU specifications from resource specs."""
        gpu_info = {
            "present": specs.get("is_gpu_present", False),
            "name": specs.get("gpu_name", "None"),
            "count": specs.get("gpu_count", 0),
            "memory_total": specs.get("memory_total", "0 MiB"),
            "memory_gb": 0.0,
            "weight": 0.0
        }
        
        # Parse memory
        if gpu_info["memory_total"]:
            try:
                memory_str = gpu_info["memory_total"]
                if isinstance(memory_str, str):
                    parts = memory_str.split()
                    if len(parts) >= 1:
                        memory_value = float(parts[0])
                        memory_unit = parts[1].lower() if len(parts) > 1 else "mib"
                        
                        if memory_unit == "mib":
                            gpu_info["memory_gb"] = memory_value / 1024.0
                        else:
                            gpu_info["memory_gb"] = memory_value
            except (ValueError, IndexError):
                pass
        
        # Get GPU weight if available
        if gpu_info["name"] and gpu_info["name"] != "None" and COMPUTE_SCORE_AVAILABLE:
            gpu_info["weight"] = get_gpu_weight(gpu_info["name"])
        
        return gpu_info
    
    def analyze_resource(self, resource: Dict[str, Any], miner_id: str) -> Dict[str, Any]:
        """Analyze a single compute resource."""
        resource_analysis = {
            'resource_id': resource.get('id', 'unknown'),
            'miner_id': miner_id,
            'validation_status': resource.get('validation_status', 'unknown'),
            'specs': resource.get('specs', {}),
            'cpu_info': {},
            'gpu_info': {},
            'resource_type': 'CPU',
            'compute_score': 0.0
        }
        
        specs = resource_analysis['specs']
        
        # Parse CPU and GPU
        resource_analysis['cpu_info'] = self.parse_cpu_specs(specs)
        resource_analysis['gpu_info'] = self.parse_gpu_specs(specs)
        
        # Determine resource type
        if resource_analysis['gpu_info']['present'] and resource_analysis['gpu_info']['count'] > 0:
            resource_analysis['resource_type'] = 'GPU'
        
        # Calculate compute score if available
        if COMPUTE_SCORE_AVAILABLE:
            try:
                resource_analysis['compute_score'] = calculate_compute_score(
                    resource_analysis['resource_type'],
                    specs
                )
            except Exception as e:
                print(f"⚠️  Warning: Could not calculate compute score for resource {resource_analysis['resource_id']}: {e}")
        
        return resource_analysis
    
    def analyze_all_miners(self, filter_gpu: bool = False, filter_cpu: bool = False):
        """Analyze all miners and their resources."""
        print("\n📊 Analyzing miner resources...")
        
        all_resources = []
        
        for miner in self.miners_data:
            self.stats['total_miners'] += 1
            
            # Get miner ID
            miner_id = str(miner.get("miner_id") or miner.get("id", "unknown"))
            
            # Check Bittensor registration
            bittensor_details = miner.get("bittensor_details")
            if bittensor_details and bittensor_details.get("miner_uid") is not None:
                self.stats['miners_registered'] += 1
                miner_uid = int(bittensor_details["miner_uid"])
                hotkey = bittensor_details.get("hotkey", "unknown")
                self.stats['miners_by_uid'][miner_uid] = {
                    'miner_id': miner_id,
                    'hotkey': hotkey,
                    'resources': []
                }
            
            # Get resources
            resources = miner.get("resource_details", [])
            if not resources:
                continue
            
            self.stats['miners_with_resources'] += 1
            
            # Analyze each resource
            for resource in resources:
                analysis = self.analyze_resource(resource, miner_id)
                
                # Apply filters
                if filter_gpu and analysis['resource_type'] != 'GPU':
                    continue
                if filter_cpu and analysis['resource_type'] != 'CPU':
                    continue
                
                all_resources.append(analysis)
                self.stats['total_resources'] += 1
                
                # Update statistics
                self.stats['verification_status'][analysis['validation_status']] += 1
                
                if analysis['resource_type'] == 'GPU':
                    self.stats['gpu_resources'] += 1
                    gpu_name = analysis['gpu_info']['name']
                    if gpu_name and gpu_name != "None":
                        self.stats['gpu_types'][gpu_name] += analysis['gpu_info']['count']
                    
                    if analysis['gpu_info']['memory_gb'] > 0:
                        self.stats['gpu_memory_distribution'].append(analysis['gpu_info']['memory_gb'])
                else:
                    self.stats['cpu_only_resources'] += 1
                
                # CPU stats
                cpu_cores = analysis['cpu_info']['cores']
                if cpu_cores > 0:
                    self.stats['cpu_cores_distribution'].append(cpu_cores)
                
                # Compute score
                if analysis['compute_score'] > 0:
                    self.stats['compute_scores'].append(analysis['compute_score'])
                
                # Add to miner's resources if registered
                if bittensor_details and bittensor_details.get("miner_uid") is not None:
                    miner_uid = int(bittensor_details["miner_uid"])
                    if miner_uid in self.stats['miners_by_uid']:
                        self.stats['miners_by_uid'][miner_uid]['resources'].append(analysis)
        
        return all_resources
    
    def print_summary(self):
        """Print summary statistics."""
        print("\n" + "=" * 80)
        print("📊 MINER RESOURCE STATISTICS SUMMARY")
        print("=" * 80)
        
        # Overall stats
        print(f"\n🔢 OVERALL STATISTICS:")
        print(f"  Total Miners: {self.stats['total_miners']}")
        print(f"  Miners with Resources: {self.stats['miners_with_resources']}")
        print(f"  Bittensor Registered Miners: {self.stats['miners_registered']}")
        print(f"  Total Compute Resources: {self.stats['total_resources']}")
        
        # Resource type breakdown
        print(f"\n💻 RESOURCE TYPE BREAKDOWN:")
        print(f"  CPU-Only Resources: {self.stats['cpu_only_resources']} ({self._percentage(self.stats['cpu_only_resources'], self.stats['total_resources'])}%)")
        print(f"  GPU Resources: {self.stats['gpu_resources']} ({self._percentage(self.stats['gpu_resources'], self.stats['total_resources'])}%)")
        
        # Verification status
        print(f"\n✅ VERIFICATION STATUS:")
        for status, count in sorted(self.stats['verification_status'].items()):
            print(f"  {status}: {count} ({self._percentage(count, self.stats['total_resources'])}%)")
        
        # GPU types
        if self.stats['gpu_types']:
            print(f"\n🎮 GPU TYPES (Top 10):")
            sorted_gpus = sorted(self.stats['gpu_types'].items(), key=lambda x: x[1], reverse=True)[:10]
            for gpu_name, count in sorted_gpus:
                print(f"  {gpu_name}: {count} GPU(s)")
        
        # CPU distribution
        if self.stats['cpu_cores_distribution']:
            cpu_cores = self.stats['cpu_cores_distribution']
            print(f"\n⚙️  CPU CORES DISTRIBUTION:")
            print(f"  Total CPUs: {len(cpu_cores)}")
            print(f"  Average Cores: {sum(cpu_cores) / len(cpu_cores):.1f}")
            print(f"  Min Cores: {min(cpu_cores)}")
            print(f"  Max Cores: {max(cpu_cores)}")
            print(f"  Median Cores: {sorted(cpu_cores)[len(cpu_cores)//2]}")
        
        # GPU memory distribution
        if self.stats['gpu_memory_distribution']:
            gpu_mem = self.stats['gpu_memory_distribution']
            print(f"\n🎮 GPU MEMORY DISTRIBUTION:")
            print(f"  Total GPUs: {len(gpu_mem)}")
            print(f"  Average Memory: {sum(gpu_mem) / len(gpu_mem):.1f} GB")
            print(f"  Min Memory: {min(gpu_mem):.1f} GB")
            print(f"  Max Memory: {max(gpu_mem):.1f} GB")
            print(f"  Median Memory: {sorted(gpu_mem)[len(gpu_mem)//2]:.1f} GB")
        
        # Compute scores
        if self.stats['compute_scores']:
            scores = self.stats['compute_scores']
            print(f"\n🏆 COMPUTE SCORE DISTRIBUTION:")
            print(f"  Resources Scored: {len(scores)}")
            print(f"  Average Score: {sum(scores) / len(scores):.2f}")
            print(f"  Min Score: {min(scores):.2f}")
            print(f"  Max Score: {max(scores):.2f}")
            print(f"  Median Score: {sorted(scores)[len(scores)//2]:.2f}")
            
            # Threshold analysis
            threshold = 0.03
            passing = [s for s in scores if s >= threshold]
            failing = [s for s in scores if s < threshold]
            print(f"\n🚨 THRESHOLD ANALYSIS (PoW >= {threshold}):")
            print(f"  Passing Resources: {len(passing)} ({self._percentage(len(passing), len(scores))}%)")
            print(f"  Failing Resources: {len(failing)} ({self._percentage(len(failing), len(scores))}%)")
        
        print("\n" + "=" * 80)
    
    def print_detailed_report(self, resources: List[Dict[str, Any]]):
        """Print detailed report of all resources."""
        print("\n" + "=" * 80)
        print("📋 DETAILED RESOURCE REPORT")
        print("=" * 80)
        
        for i, resource in enumerate(resources, 1):
            print(f"\n--- Resource #{i} ---")
            print(f"Resource ID: {resource['resource_id']}")
            print(f"Miner ID: {resource['miner_id']}")
            print(f"Type: {resource['resource_type']}")
            print(f"Validation Status: {resource['validation_status']}")
            print(f"Compute Score: {resource['compute_score']:.4f}")
            
            # CPU info
            cpu = resource['cpu_info']
            print(f"\nCPU:")
            print(f"  Model: {cpu['model']}")
            print(f"  Cores: {cpu['cores']}")
            print(f"  Speed: {cpu['speed_mhz']} MHz")
            print(f"  Threads/Core: {cpu['threads_per_core']}")
            print(f"  Total Threads: {cpu['total_threads']}")
            
            # GPU info
            if resource['resource_type'] == 'GPU':
                gpu = resource['gpu_info']
                print(f"\nGPU:")
                print(f"  Name: {gpu['name']}")
                print(f"  Count: {gpu['count']}")
                print(f"  Memory: {gpu['memory_gb']:.1f} GB")
                print(f"  Weight: {gpu['weight']:.2f}")
        
        print("\n" + "=" * 80)
    
    def export_to_csv(self, resources: List[Dict[str, Any]], filename: str = None):
        """Export resource data to CSV."""
        if filename is None:
            filename = f"miner_resources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            import csv
            
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = [
                    'resource_id', 'miner_id', 'resource_type', 'validation_status',
                    'compute_score', 'cpu_model', 'cpu_cores', 'cpu_speed_mhz',
                    'cpu_threads', 'gpu_name', 'gpu_count', 'gpu_memory_gb', 'gpu_weight'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for resource in resources:
                    writer.writerow({
                        'resource_id': resource['resource_id'],
                        'miner_id': resource['miner_id'],
                        'resource_type': resource['resource_type'],
                        'validation_status': resource['validation_status'],
                        'compute_score': resource['compute_score'],
                        'cpu_model': resource['cpu_info']['model'],
                        'cpu_cores': resource['cpu_info']['cores'],
                        'cpu_speed_mhz': resource['cpu_info']['speed_mhz'],
                        'cpu_threads': resource['cpu_info']['total_threads'],
                        'gpu_name': resource['gpu_info']['name'],
                        'gpu_count': resource['gpu_info']['count'],
                        'gpu_memory_gb': resource['gpu_info']['memory_gb'],
                        'gpu_weight': resource['gpu_info']['weight']
                    })
            
            print(f"\n✅ Data exported to: {filename}")
            
        except Exception as e:
            print(f"\n❌ Error exporting to CSV: {e}")
    
    def _percentage(self, part: int, total: int) -> float:
        """Calculate percentage."""
        return (part / total * 100) if total > 0 else 0.0


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Analyze Polaris Validator miner resources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_miner_resources.py
  python analyze_miner_resources.py --detailed
  python analyze_miner_resources.py --filter-gpu --export-csv
  python analyze_miner_resources.py --detailed --export-csv resources.csv
        """
    )
    
    parser.add_argument('--detailed', action='store_true',
                        help='Print detailed report for each resource')
    parser.add_argument('--export-csv', nargs='?', const=True,
                        help='Export data to CSV file (optional: specify filename)')
    parser.add_argument('--filter-gpu', action='store_true',
                        help='Show only GPU resources')
    parser.add_argument('--filter-cpu', action='store_true',
                        help='Show only CPU resources')
    
    args = parser.parse_args()
    
    # Validate filters
    if args.filter_gpu and args.filter_cpu:
        print("❌ Error: Cannot use both --filter-gpu and --filter-cpu")
        sys.exit(1)
    
    print("=" * 80)
    print("🔍 POLARIS VALIDATOR - MINER RESOURCE ANALYZER")
    print("=" * 80)
    
    # Initialize analyzer
    analyzer = MinerResourceAnalyzer()
    
    # Fetch miners
    if not analyzer.fetch_miners():
        print("❌ Failed to fetch miners data. Exiting.")
        sys.exit(1)
    
    # Analyze resources
    resources = analyzer.analyze_all_miners(
        filter_gpu=args.filter_gpu,
        filter_cpu=args.filter_cpu
    )
    
    print(f"✅ Analyzed {len(resources)} resources")
    
    # Print summary
    analyzer.print_summary()
    
    # Print detailed report if requested
    if args.detailed:
        analyzer.print_detailed_report(resources)
    
    # Export to CSV if requested
    if args.export_csv:
        filename = args.export_csv if isinstance(args.export_csv, str) else None
        analyzer.export_to_csv(resources, filename)
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
