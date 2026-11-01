"""The budget records as the API shows them."""

from collections.abc import Mapping, Sequence

from app.domain.catalogue import BudgetRecord, BudgetView, FigureView, SourceRef


def budget_views(
    records: Sequence[BudgetRecord], sources: Mapping[str, SourceRef]
) -> list[BudgetView]:
    """Newest budget first, then by title. A record with no Actual figure is flagged: its money is
    an allocation or an estimate, not spending."""
    views = [
        BudgetView(
            id=record.id,
            budget_year=record.budget_year,
            level=record.level,
            state=record.state,
            sector=record.sector,
            kind=record.kind,
            title=record.title,
            department=record.department,
            last_verified=record.last_verified,
            summary=record.summary,
            meaning=record.meaning,
            figures=[
                FigureView(
                    basis=f.basis,
                    year=f.year,
                    amount=f.amount,
                    unit=f.unit,
                    evidence=f.evidence,
                )
                for f in sorted(record.figures, key=lambda f: (f.year, f.basis), reverse=True)
            ],
            statements=record.statements,
            sources=[sources[i] for i in record.source_ids if i in sources],
            not_actual_spending=not any(f.basis == "actual" for f in record.figures),
        )
        for record in records
    ]
    views.sort(key=lambda v: v.title)
    views.sort(key=lambda v: v.budget_year, reverse=True)  # stable: titles stay in order
    return views
