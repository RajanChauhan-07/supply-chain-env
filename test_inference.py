import sys
import traceback
print("Starting script...")
try:
    import inference
    print("Imported inference")
    inference.main()
    print("Finished inference.main()")
except Exception as e:
    print("Caught Exception:", repr(e))
    traceback.print_exc()
print("End of script")
