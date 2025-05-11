import sys
print("Python version:", sys.version)
print("Path:", sys.path)

print("\nTrying to import replit modules:")
try:
    import replit
    print("Replit package imported successfully")
    print("Available modules in replit:", dir(replit))
    
    try:
        from replit.object_storage import Client
        print("Successfully imported Client from replit.object_storage")
        
        try:
            client = Client()
            print("Successfully created Client instance")
            
            # Test if we can list objects
            objects = client.list()
            print(f"Found {len(objects)} objects")
            
        except Exception as e:
            print(f"Error creating Client instance: {str(e)}")
    except ImportError as e:
        print(f"Error importing from replit.object_storage: {str(e)}")
except ImportError as e:
    print(f"Error importing replit: {str(e)}")

# Try alternative import paths mentioned in documentation
print("\nTrying alternative imports:")
try:
    import replit_object_storage
    print("Successfully imported replit_object_storage")
except ImportError as e:
    print(f"Error importing replit_object_storage: {str(e)}")

try:
    from replit import extensions
    print("Extensions module exists:", extensions)
    try:
        from replit.extensions import objectstorage
        print("Successfully imported from replit.extensions.objectstorage")
    except ImportError as e:
        print(f"Error importing from replit.extensions.objectstorage: {str(e)}")
except ImportError as e:
    print(f"Error importing replit.extensions: {str(e)}")