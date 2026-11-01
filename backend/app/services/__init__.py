"""Domain logic, one subpackage per stage of the document pipeline in SPEC section 6.

Routers in ``app.api`` stay thin and call into these packages.
Nothing in here may import from ``app.api``.
"""
