import py_compile
import os

def check_syntax(directory):
    errors = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    py_compile.compile(path, doraise=True)
                except Exception as e:
                    errors.append(str(e))
    return errors

if __name__ == "__main__":
    errs = check_syntax("d:\\New folder (7)\\billflow-pro\\backend")
    if errs:
        print("SYNTAX ERRORS FOUND:")
        for e in errs:
            print(e)
    else:
        print("NO SYNTAX ERRORS")
        
    try:
        from backend.app import app
        print("App imported successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()
