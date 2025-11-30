import json
import os
import re

class WorkflowManager:
    def __init__(self, workflows_dir="workflows"):
        self.workflows_dir = workflows_dir
        self.workflows = {} # name -> json_content
        self.reload_workflows()

    def reload_workflows(self):
        self.workflows = {}
        if not os.path.exists(self.workflows_dir):
            os.makedirs(self.workflows_dir)
            return

        for filename in os.listdir(self.workflows_dir):
            if filename.endswith(".json"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(self.workflows_dir, filename)
                try:
                    with open(path, 'r') as f:
                        content = json.load(f)
                        if "nodes" in content and "links" in content:
                            print(f"Warning: {filename} appears to be in UI format, not API format. Skipping.")
                            continue
                        self.workflows[name] = content
                except Exception as e:
                    print(f"Error loading workflow {filename}: {e}")

    def get_workflow_names(self):
        return list(self.workflows.keys())

    def get_workflow(self, name):
        return self.workflows.get(name)

    def get_placeholders(self, name):
        """Extracts %PLACEHOLDERS% from the workflow."""
        workflow = self.workflows.get(name)
        if not workflow:
            return []
        
        # Convert to string to search
        text = json.dumps(workflow)
        # Find all %WORD% patterns
        matches = re.findall(r'%([A-Z_]+)%', text)
        return sorted(list(set(matches)))

    def process_workflow(self, name, values):
        """
        Replaces placeholders with values.
        values: dict of {PLACEHOLDER: value}
        """
        workflow = self.workflows.get(name)
        if not workflow:
            return None
            
        # Deep copy to avoid modifying the original
        import copy
        workflow_copy = copy.deepcopy(workflow)
        
        def recursive_replace(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    obj[k] = recursive_replace(v)
            elif isinstance(obj, list):
                for i in range(len(obj)):
                    obj[i] = recursive_replace(obj[i])
            elif isinstance(obj, str):
                # Check if it matches a placeholder exactly
                # e.g. "%SEED%"
                # If so, we can replace with the typed value
                for key, val in values.items():
                    placeholder = f"%{key}%"
                    if obj == placeholder:
                        # Try to convert to number if it looks like one
                        try:
                            if "." in val:
                                return float(val)
                            else:
                                return int(val)
                        except ValueError:
                            return val
                    elif placeholder in obj:
                         # Partial replacement (must remain string)
                         obj = obj.replace(placeholder, str(val))
            return obj

        return recursive_replace(workflow_copy)
