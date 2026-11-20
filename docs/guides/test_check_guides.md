# Test the code map

[This test](../../tools/test_check_guides.py) makes two tiny source files and their guides inside a temporary directory. Its caller is Python unittest discovery. It changes one part of the sample map at a time, then reads the messages returned by the checker.

Set a breakpoint at `index.write_text(mapping, ...)`. In the duplicate case the second source points to the first source's guide. Continue into [the checker](../../tools/check_guides.py) and inspect the observed paths. The final empty-file case tests a different failure with the same map. Run `python -m unittest discover -s tools -p test_check_guides.py -v` from the checkout.
