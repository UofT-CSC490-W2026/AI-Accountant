from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from services.agent.graph.state import (
    DISAMBIGUATOR, DEBIT_CLASSIFIER, CREDIT_CLASSIFIER,
    DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
    APPROVER, DIAGNOSTICIAN,
)


# ── Agent name constants for new agents ──────────────────────────────────

AMBIGUITY_DETECTOR = "ambiguity_detector"
COMPLEXITY_DETECTOR = "complexity_detector"
TAX_SPECIALIST = "tax_specialist"
DECISION_MAKER = "decision_maker"
ENTRY_DRAFTER = "entry_drafter"


# ── Ambiguity Detector ───────────────────────────────────────────────────

class Ambiguity(BaseModel):
    aspect: str = Field(description="The ambiguous aspect in one phrase")
    why_entry_depends_on_clarification: str | None = Field(default=None, description="Concise: how the journal entry structure changes depending on the answer")
    why_ambiguity_not_resolved_by_given_info: str | None = Field(default=None, description="Concise: why the transaction text, conventions, and context don't resolve it")
    clarification_question: str | None = Field(default=None, description="One question answerable by the person who initiated the transaction")
    options: list[str] | None = Field(default=None, description="The possible interpretations")
    resolved: bool = Field(description="True if resolved by text, conventions, or context")


class AmbiguityDetectorOutput(BaseModel):
    ambiguities: list[Ambiguity] = Field(description="All identified ambiguities, resolved and unresolved")


# ── Complexity Detector ──────────────────────────────────────────────────

class ComplexityFlag(BaseModel):
    aspect: str = Field(description="The complex aspect in one phrase")
    why_llm_cannot_do_this: str | None = Field(default=None, description="Concise: what knowledge or capability is missing")
    what_is_best_llm_can_do: str | None = Field(default=None, description="Concise: the closest valid entry the LLM can produce")
    skeptical: bool = Field(description="True if the LLM lacks the knowledge to handle this correctly")


class ComplexityDetectorOutput(BaseModel):
    flags: list[ComplexityFlag] = Field(description="All aspects assessed for complexity")


# ── Per-type taxonomy categories ─────────────────────────────────────────

ASSET_CATEGORIES = Literal[
    "Land", "Buildings", "Machinery", "Motor vehicles", "Office equipment",
    "Fixtures and fittings", "Construction in progress", "Site improvements",
    "Right-of-use assets", "Goodwill", "Intangible assets", "Investment property",
    "Investments — equity method", "Investments — FVTPL", "Investments — FVOCI",
    "Deferred tax assets", "Non-current loans receivable", "Long-term deposits",
    "Non-current prepayments", "Inventories — raw materials",
    "Inventories — work in progress", "Inventories — finished goods",
    "Inventories — merchandise", "Cash and cash equivalents", "Trade receivables",
    "Contract assets", "Prepaid expenses", "Tax assets",
    "Short-term loans receivable", "Short-term deposits", "Restricted cash",
]

LIABILITY_CATEGORIES = Literal[
    "Trade payables", "Accrued liabilities", "Employee benefits payable",
    "Warranty provisions", "Legal and restructuring provisions", "Tax liabilities",
    "Short-term borrowings", "Current lease liabilities", "Deferred income",
    "Contract liabilities", "Dividends payable", "Long-term borrowings",
    "Non-current lease liabilities", "Pension obligations",
    "Decommissioning provisions", "Deferred tax liabilities",
]

EQUITY_CATEGORIES = Literal[
    "Issued capital", "Share premium", "Retained earnings", "Treasury shares",
    "Revaluation surplus", "Translation reserve", "Hedging reserve",
]

REVENUE_CATEGORIES = Literal[
    "Revenue from sale of goods", "Revenue from rendering of services",
    "Interest income", "Dividend income", "Share of profit of associates",
    "Gains (losses) on disposals", "Fair value gains (losses)",
    "Foreign exchange gains (losses)", "Rental income", "Government grant income",
]

EXPENSE_CATEGORIES = Literal[
    "Cost of sales", "Employee benefits expense", "Depreciation expense",
    "Amortisation expense", "Impairment loss", "Advertising expense",
    "Professional fees expense", "Travel expense", "Utilities expense",
    "Repairs and maintenance expense", "Services expense", "Insurance expense",
    "Communication expense", "Transportation expense", "Warehousing expense",
    "Occupancy expense", "Interest expense", "Income tax expense",
    "Property tax expense", "Payroll tax expense",
    "Research and development expense", "Entertainment expense",
    "Donations expense", "Royalty expense", "Casualty loss",
    "Penalties and fines",
]

DIVIDEND_CATEGORIES = Literal[
    "Dividends declared",
]


# ── Per-type classified lines ────────────────────────────────────────────

class AssetLine(BaseModel):
    reason: str = Field(description="Why these asset lines exist")
    category: ASSET_CATEGORIES = Field(description="IFRS asset category")
    count: int = Field(description="Number of journal lines for this category")


class LiabilityLine(BaseModel):
    reason: str = Field(description="Why these liability lines exist")
    category: LIABILITY_CATEGORIES = Field(description="IFRS liability category")
    count: int = Field(description="Number of journal lines for this category")


class EquityLine(BaseModel):
    reason: str = Field(description="Why these equity lines exist")
    category: EQUITY_CATEGORIES = Field(description="IFRS equity category")
    count: int = Field(description="Number of journal lines for this category")


class RevenueLine(BaseModel):
    reason: str = Field(description="Why these revenue/income lines exist")
    category: REVENUE_CATEGORIES = Field(description="IFRS revenue/income category")
    count: int = Field(description="Number of journal lines for this category")


class ExpenseLine(BaseModel):
    reason: str = Field(description="Why these expense lines exist")
    category: EXPENSE_CATEGORIES = Field(description="IFRS expense category")
    count: int = Field(description="Number of journal lines for this category")


class DividendLine(BaseModel):
    reason: str = Field(description="Why these dividend lines exist")
    category: DIVIDEND_CATEGORIES = Field(description="IFRS dividend category")
    count: int = Field(description="Number of journal lines for this category")


# ── Debit Classifier ────────────────────────────────────────────────────

class DebitClassifierOutput(BaseModel):
    asset_increase: list[AssetLine] = Field(default_factory=list, description="Lines that increase asset balances")
    dividend_increase: list[DividendLine] = Field(default_factory=list, description="Lines that increase dividend/drawing balances")
    expense_increase: list[ExpenseLine] = Field(default_factory=list, description="Lines that increase expense balances")
    liability_decrease: list[LiabilityLine] = Field(default_factory=list, description="Lines that decrease liability balances")
    equity_decrease: list[EquityLine] = Field(default_factory=list, description="Lines that decrease equity balances")
    revenue_decrease: list[RevenueLine] = Field(default_factory=list, description="Lines that decrease revenue balances")


# ── Credit Classifier ───────────────────────────────────────────────────

class CreditClassifierOutput(BaseModel):
    liability_increase: list[LiabilityLine] = Field(default_factory=list, description="Lines that increase liability balances")
    equity_increase: list[EquityLine] = Field(default_factory=list, description="Lines that increase equity balances")
    revenue_increase: list[RevenueLine] = Field(default_factory=list, description="Lines that increase revenue balances")
    asset_decrease: list[AssetLine] = Field(default_factory=list, description="Lines that decrease asset balances")
    dividend_decrease: list[DividendLine] = Field(default_factory=list, description="Lines that decrease dividend/drawing balances")
    expense_decrease: list[ExpenseLine] = Field(default_factory=list, description="Lines that decrease expense balances")


# ── Tax Specialist ───────────────────────────────────────────────────────

class TaxSpecialistOutput(BaseModel):
    reasoning: str = Field(description="Concise: what the transaction text says about tax and what treatment applies")
    tax_mentioned: bool = Field(description="True if the transaction text explicitly mentions tax")
    taxable: bool = Field(description="True if this transaction type is taxable")
    add_tax_lines: bool = Field(description="True if the entry should include separate tax lines")
    tax_rate: float | None = Field(default=None, description="Tax rate from the transaction text, e.g. 0.10 for 10%")
    tax_amount: float | None = Field(default=None, description="Tax amount from the transaction text")
    treatment: Literal["recoverable", "non_recoverable", "not_applicable"] = Field(description="How to record the tax: as receivable, as part of expense, or not applicable")


# ── Decision Maker ───────────────────────────────────────────────────────

class DecisionMakerOutput(BaseModel):
    # 1. Ambiguity review
    ambiguity_assessment: str = Field(description="Concise: for each unresolved ambiguity, does it actually prevent building the entry?")
    missing_info_decision: bool = Field(description="True if missing facts prevent a correct entry")
    clarification_questions: list[str] = Field(description="Questions to resolve missing facts. Empty if not missing_info.")

    # 2. Complexity review
    complexity_assessment: str = Field(description="Concise: for each flagged complexity, is the LLM truly unable to handle this?")
    llm_stuck: bool = Field(description="True if LLM lacks knowledge to produce a correct entry")
    stuck_reason: str | None = Field(default=None, description="Concise: what knowledge gap prevents the entry")

    # 3. Classification review
    classification_assessment: str = Field(description="Concise: for each classified line, is the reason valid and category correct?")
    debit_approved: bool = Field(description="True if debit classification is accepted as-is")
    override_debit: list[int] | None = Field(default=None, description="Corrected 6-slot debit line counts [a,d,e,l,eq,r]. Only if debit_approved is false.")
    credit_approved: bool = Field(description="True if credit classification is accepted as-is")
    override_credit: list[int] | None = Field(default=None, description="Corrected 6-slot credit line counts [l,eq,r,a,d,e]. Only if credit_approved is false.")

    # 4. Final decision
    decision_rationale: str = Field(description="Concise: synthesize all assessments into a final judgment")
    decision: Literal["proceed", "missing_info", "llm_stuck"] = Field(description="Final decision after all assessments")


# ── Entry Drafter ────────────────────────────────────────────────────────

class JournalLine(BaseModel):
    type: Literal["debit", "credit"] = Field(description="Debit or credit")
    account_name: str = Field(description="Account name derived from the transaction description")
    amount: float = Field(description="Dollar amount for this line")


class EntryDrafterOutput(BaseModel):
    reason: str = Field(description="Concise: why these accounts and amounts, derived from transaction text")
    lines: list[JournalLine] = Field(description="Journal entry lines. Total debits must equal total credits.")


# ── Approver ─────────────────────────────────────────────────────────────

class ApproverOutput(BaseModel):
    reason: str = Field(description="Concise: what specific checks passed or which specific issue was found")
    decision: Literal["APPROVED", "REJECTED", "STUCK"] = Field(description="Judgment on the entry")
    confidence: Literal["VERY_CONFIDENT", "SOMEWHAT_CONFIDENT", "SOMEWHAT_UNCERTAIN", "VERY_UNCERTAIN"] = Field(description="How certain the judgment is")


# ── Diagnostician ────────────────────────────────────────────────────────

class FixPlan(BaseModel):
    agent: int = Field(description="Agent index 1-5 (not 0)")
    fix_context: str = Field(description="Concise: what to fix and how")


class DiagnosticianOutput(BaseModel):
    reasoning: str = Field(description="Concise: trace the error to its root cause agent and explain why")
    decision: Literal["FIX", "STUCK"] = Field(description="Whether the error is fixable by rerun or needs human intervention")
    fix_plans: list[FixPlan] = Field(description="Fix instructions per root cause agent. Empty if STUCK.")
    stuck_reason: str | None = Field(default=None, description="Concise: why this cannot be resolved by the pipeline")


# ── Legacy corrector schemas (for variants with correction) ──────────────

class DebitCorrectorOutput(BaseModel):
    reason: str = Field(description="Concise: what was wrong with the initial structure and how you fixed it, or why it was already correct")
    asset_increase_reason: str = Field(description="Concise: which assets increase and why this count")
    asset_increase_count: int = Field(description="Number of asset increase lines")
    dividend_increase_reason: str = Field(description="Concise: which dividends/drawings increase and why this count")
    dividend_increase_count: int = Field(description="Number of dividend increase lines")
    expense_increase_reason: str = Field(description="Concise: which expenses increase and why this count")
    expense_increase_count: int = Field(description="Number of expense increase lines")
    liability_decrease_reason: str = Field(description="Concise: which liabilities decrease and why this count")
    liability_decrease_count: int = Field(description="Number of liability decrease lines")
    equity_decrease_reason: str = Field(description="Concise: which equity accounts decrease and why this count")
    equity_decrease_count: int = Field(description="Number of equity decrease lines")
    revenue_decrease_reason: str = Field(description="Concise: which revenues decrease and why this count")
    revenue_decrease_count: int = Field(description="Number of revenue decrease lines")


class CreditCorrectorOutput(BaseModel):
    reason: str = Field(description="Concise: what was wrong with the initial structure and how you fixed it, or why it was already correct")
    liability_increase_reason: str = Field(description="Concise: which liabilities increase and why this count")
    liability_increase_count: int = Field(description="Number of liability increase lines")
    equity_increase_reason: str = Field(description="Concise: which equity accounts increase and why this count")
    equity_increase_count: int = Field(description="Number of equity increase lines")
    revenue_increase_reason: str = Field(description="Concise: which revenues increase and why this count")
    revenue_increase_count: int = Field(description="Number of revenue increase lines")
    asset_decrease_reason: str = Field(description="Concise: which assets decrease and why this count")
    asset_decrease_count: int = Field(description="Number of asset decrease lines")
    dividend_decrease_reason: str = Field(description="Concise: which dividends/drawings decrease and why this count")
    dividend_decrease_count: int = Field(description="Number of dividend decrease lines")
    expense_decrease_reason: str = Field(description="Concise: which expenses decrease and why this count")
    expense_decrease_count: int = Field(description="Number of expense decrease lines")


# ── Model registry ──────────────────────────────────────────────────────

_MODELS: dict[str, type[BaseModel]] = {
    AMBIGUITY_DETECTOR: AmbiguityDetectorOutput,
    COMPLEXITY_DETECTOR: ComplexityDetectorOutput,
    DEBIT_CLASSIFIER: DebitClassifierOutput,
    CREDIT_CLASSIFIER: CreditClassifierOutput,
    TAX_SPECIALIST: TaxSpecialistOutput,
    DECISION_MAKER: DecisionMakerOutput,
    ENTRY_DRAFTER: EntryDrafterOutput,
    DEBIT_CORRECTOR: DebitCorrectorOutput,
    CREDIT_CORRECTOR: CreditCorrectorOutput,
    APPROVER: ApproverOutput,
    DIAGNOSTICIAN: DiagnosticianOutput,
    # Legacy aliases
    DISAMBIGUATOR: AmbiguityDetectorOutput,
    ENTRY_BUILDER: EntryDrafterOutput,
}


# ── Helpers ──────────────────────────────────────────────────────────────

DEBIT_SLOTS = ["asset_increase", "dividend_increase", "expense_increase",
               "liability_decrease", "equity_decrease", "revenue_decrease"]
CREDIT_SLOTS = ["liability_increase", "equity_increase", "revenue_increase",
                "asset_decrease", "dividend_decrease", "expense_decrease"]


def extract_tuple(output: dict, slots: list[str]) -> tuple[int, ...]:
    """Extract a 6-tuple from named slot fields.

    Supports three formats:
    - V4 (taxonomy): slot is a list of dicts with "count" → sum of counts
    - V3 (flattened): slot_count field → int value
    - V2 (nested): slot is a dict with "count" key → dict["count"]
    """
    counts = []
    for s in slots:
        val = output.get(s)
        if isinstance(val, list):
            counts.append(sum(item.get("count", 1) for item in val if isinstance(item, dict)))
        elif isinstance(val, dict):
            counts.append(val.get("count", 0))
        elif f"{s}_count" in output:
            counts.append(output[f"{s}_count"])
        else:
            counts.append(0)
    return tuple(counts)


def extract_debit_tuple(output: dict) -> tuple[int, ...]:
    return extract_tuple(output, DEBIT_SLOTS)


def extract_credit_tuple(output: dict) -> tuple[int, ...]:
    return extract_tuple(output, CREDIT_SLOTS)


# ── Parser ───────────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    """Remove markdown code fences if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


def parse_json_output(agent_name: str, raw: str) -> dict | None:
    """Parse an LLM JSON output string and validate against agent schema."""
    model = _MODELS.get(agent_name)
    if model is None:
        return None

    try:
        cleaned = _strip_fences(raw)
        result = model.model_validate_json(cleaned)
        return result.model_dump()
    except (ValidationError, ValueError):
        return None
