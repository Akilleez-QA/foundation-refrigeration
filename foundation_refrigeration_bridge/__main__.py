import importlib
import sys

sys.dont_write_bytecode = True
main = importlib.import_module(".server", __package__).main

raise SystemExit(main())
