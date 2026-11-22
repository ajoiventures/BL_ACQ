# Document-to-offer layer verification

Source: [test_document_offer_layer.py](../../tests/test_document_offer_layer.py).

Run:

```sh
python -m unittest discover -s tests -p test_document_offer_layer.py -v
```

The tests run the complete synthetic four-state workflow with a real temporary
SQLite store, empty AI credentials and network socket construction forbidden.
They verify reviewed $35,000 to $55,000 quote propagation, explicit scenario
buffers, unchanged acquisition probabilities, input immutability, provenance,
and financial failure after costs rise.

Adverse cases cover forbidden probability/policy bindings, duplicate and
unknown targets, invalid units/currency/money, changed live-counter and new
offer terms, external probability context changes, synthetic-status
propagation, unreviewed exports, content-tampered reports and overwrite protection.
The R exchange check inspects exact fraction strings and unknown EV fields;
it is a Python contract test, not a claim that R executed.
