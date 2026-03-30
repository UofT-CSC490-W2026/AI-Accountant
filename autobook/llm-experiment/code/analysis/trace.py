"""Extract agent reasoning trace from a result JSON.

Usage:
    python trace.py results/stage3/with_disambiguation/int_11_land_instalment_discount.json
    python trace.py results/stage3/with_disambiguation/int_11_land_instalment_discount.json --compact
"""
import json
import sys
from pathlib import Path


def _fmt_lines(lines):
    if not lines:
        return "  (no lines)"
    out = []
    for l in lines:
        out.append(f"  {l['type']:6s} {l.get('account_name','?'):45s} ${l.get('amount',0):>14,.2f}")
    return "\n".join(out)


def _fmt_ambiguities(ambiguities):
    if not ambiguities:
        return "  (none)"
    out = []
    for a in ambiguities:
        status = "RESOLVED" if a.get("resolved") else "UNRESOLVED"
        out.append(f"  [{status}] {a.get('aspect', '?')}")
        if a.get("resolved"):
            out.append(f"    Resolution: {a.get('resolution', '?')}")
        else:
            opts = a.get("options", [])
            if opts:
                out.append(f"    Options: {opts}")
            q = a.get("clarification_question")
            if q:
                out.append(f"    Question: {q}")
            why = a.get("why_not_resolved")
            if why:
                out.append(f"    Why not resolved: {why}")
    return "\n".join(out)


def trace(data: dict, compact: bool = False):
    tc_id = data.get("test_case_id", "?")
    variant = data.get("variant_name", "?")
    decision = data.get("final_decision", "?")
    ps = data.get("pipeline_state", {})

    print(f"{'='*70}")
    print(f"Test Case: {tc_id}")
    print(f"Variant:   {variant}")
    print(f"Decision:  {decision}")
    print(f"{'='*70}")

    # Transaction
    tx = data.get("pipeline_state", {}).get("transaction_text") or "?"
    if tx == "?":
        # Try to get from top level or other locations
        pass

    # Debit/Credit tuples
    dt = data.get("debit_tuple")
    ct = data.get("credit_tuple")
    dt_match = data.get("debit_tuple_exact_match")
    ct_match = data.get("credit_tuple_exact_match")
    print(f"\nFinal Tuples:")
    print(f"  Debit:  {dt}  {'✓' if dt_match else '✗'}")
    print(f"  Credit: {ct}  {'✓' if ct_match else '✗'}")

    # Agent order for multi-agent
    agent_order = [
        ("Disambiguator", "output_disambiguator"),
        ("Debit Classifier", "output_debit_classifier"),
        ("Credit Classifier", "output_credit_classifier"),
        ("Debit Corrector", "output_debit_corrector"),
        ("Credit Corrector", "output_credit_corrector"),
        ("Entry Builder", "output_entry_builder"),
        ("Approver", "output_approver"),
        ("Diagnostician", "output_diagnostician"),
    ]

    for agent_name, key in agent_order:
        outputs = ps.get(key, [])
        if not outputs:
            continue

        # Skip correctors if output is identical to classifier (passthrough)
        if key == "output_debit_corrector":
            cls = ps.get("output_debit_classifier", [])
            if cls and outputs and cls[-1] == outputs[-1]:
                continue
        if key == "output_credit_corrector":
            cls = ps.get("output_credit_classifier", [])
            if cls and outputs and cls[-1] == outputs[-1]:
                continue

        for i, out in enumerate(outputs):
            if out is None:
                continue
            iter_label = f" (iter {i})" if len(outputs) > 1 else ""
            print(f"\n{'─'*70}")
            print(f"Agent: {agent_name}{iter_label}")
            print(f"{'─'*70}")

            if key == "output_disambiguator":
                ambiguities = out.get("ambiguities", [])
                print(f"Ambiguities ({len(ambiguities)}):")
                print(_fmt_ambiguities(ambiguities))

            elif key in ("output_debit_classifier", "output_credit_classifier",
                         "output_debit_corrector", "output_credit_corrector"):
                t = out.get("tuple", "?")
                r = out.get("reason", "?")
                print(f"Tuple:  {t}")
                print(f"Reason: {r}")

            elif key == "output_entry_builder":
                lines = out.get("lines", [])
                rationale = out.get("rationale", "?")
                d = out.get("decision")
                cq = out.get("clarification_questions")
                dr = out.get("disambiguator_responses")

                if dr:
                    print(f"Disambiguator Responses:")
                    for resp in dr:
                        print(f"  [{resp.get('action','?').upper()}] {resp.get('aspect','?')}")
                        print(f"    {resp.get('reason','?')}")

                print(f"Rationale: {rationale}")
                print(f"Entry:")
                print(_fmt_lines(lines))
                if d:
                    print(f"Decision: {d}")
                if cq:
                    print(f"Clarification Questions: {cq}")

            elif key == "output_approver":
                d = out.get("decision", "?")
                r = out.get("reason", "?")
                c = out.get("confidence", "?")
                print(f"Decision:   {d}")
                print(f"Confidence: {c}")
                print(f"Reason:     {r}")

            elif key == "output_diagnostician":
                d = out.get("decision", "?")
                fps = out.get("fix_plans", [])
                sr = out.get("stuck_reason")
                reasoning = out.get("reasoning", "?")
                print(f"Reasoning: {reasoning}")
                print(f"Decision:  {d}")
                if fps:
                    print(f"Fix Plans:")
                    for fp in fps:
                        print(f"  Agent {fp.get('agent')}: {fp.get('fix_context')}")
                if sr:
                    print(f"Stuck Reason: {sr}")

    # Journal entry summary
    je = data.get("journal_entry")
    print(f"\n{'='*70}")
    print(f"Final Journal Entry:")
    if je and isinstance(je, dict) and je.get("lines"):
        print(_fmt_lines(je["lines"]))
    elif je is None:
        print("  (null — no entry produced)")
    else:
        print(f"  {je}")

    # Error
    err = data.get("error")
    if err:
        print(f"\nError: {err}")

    print(f"{'='*70}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python trace.py <result.json> [--compact]")
        sys.exit(1)

    path = Path(sys.argv[1])
    compact = "--compact" in sys.argv

    data = json.loads(path.read_text())
    trace(data, compact)


if __name__ == "__main__":
    main()
