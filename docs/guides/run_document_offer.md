# Run the document-to-offer demonstration

Source: [run_document_offer.py](../../tools/run_document_offer.py).

From the project root:

```sh
python tools/run_document_offer.py --output .runs/document-offer.json --r-export .runs/document-offer-r
```

Use new output paths for another run. The command protects existing outputs.
The default CPU path requires no AI credentials, model service or network.

The two input documents are explicitly synthetic native JSON fixtures. This
command is not OCR and does not claim to have processed a real contractor quote.
It creates a temporary SQLite evidence store and simulates four states:

1. Initial quote entered but unreviewed: adjusted underwriting withheld.
2. Initial $35,000 quote reviewed: original financial case reproduced.
3. Revised $55,000 quote entered: the older accepted value is superseded;
   adjusted underwriting remains withheld while the revision awaits review.
4. Revision reviewed: all renovation scenarios change using their explicit
   original analyst buffers of $0, $0, $10,000 and $20,000 above the quote.

For offer B, the final baseline profit is $27,000 and conditional expected
profit is $16,700. Every scenario increases renovation expense by $20,000;
the scenario probabilities are unchanged assumptions. No listed offer meets
the original $45,000 baseline requirement after that change. These results
illustrate controlled propagation, not a new market forecast.

The JSON export retains both underlying calculations and the source-linked
changes. The optional CSV/manifest export is a versioned input to future R
review. It does not run R; the temporary demo database is discarded after the
fully described reports are produced. A caller needing durable evidence uses
the [evidence store](document_evidence.md) with its own database path.

`--backend cuda` explicitly requests the available CUDA adapter. Missing CuPy
or a working device is an error. No GPU speedup is claimed by the example.
