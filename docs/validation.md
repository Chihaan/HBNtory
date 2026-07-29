# Stock Validation Rules

This document explains where stock validation is enforced in the
Backoffice and why each rule is placed where it is.

## Where validation lives

The Backoffice is organised in three layers. The **view** speaks HTTP:
it reads the form, converts `"5"` into `5`, and knows who is logged in
through `current_user`. The **service layer** (`backoffice/services/`)
speaks business: it decides whether an operation is allowed and applies
it. The **model** (`models.py`) only describes what a stock row is and
its constraints; it does not run when a request arrives.

All stock validation lives in the service layer.

It is not placed in the view, because it would have to be repeated in
every route, and any caller that is not a view — a script, a test, a
future MCP server — would bypass it. A rule that can be skipped by
changing the caller is not a rule.

It is not placed in the model either. A model validator cannot make the
network call needed to check a product against the external API, and it
knows nothing about the acting user. The model describes a row, not an
operation.

The service layer is the only place that sees both **who acts** and
**what is written**. It is the narrowest passage every write must go
through, so validation happens there, before anything reaches the
database.

## Database constraints vs application checks

Two layers protect the data, and they protect different things.

The database enforces the **final state**. A `CHECK (quantity >= 0)`
constraint guarantees that no stored quantity is ever negative, whatever
code writes to the table. This is the last line of defence and it cannot
be bypassed.

The service enforces the **meaning of the operation**. A `CHECK`
constraint only sees the resulting value, not the intent. Consider a
removal with a negative quantity:

    current stock = 4
    remove_stock(quantity=-5)
    4 - (-5) = 9

The result, 9, is positive. The constraint is satisfied and PostgreSQL
accepts it — yet the employee has just turned a removal into a hidden
addition. The database never saw a violation because none happened. Only
an application check ("quantity must be a strictly positive integer")
catches this, because only the service knows the operation was meant to
be a removal.

The constraint guards the stored value; the service guards the intent.

## Why branch is not a parameter

The services never take `branch_id` as an argument. It is always read
from the authenticated user:

    branch_id = _user_branch_id(user)

If `branch_id` were a parameter, the caller would decide which branch to
touch, and security would depend on every route remembering to check
that the user is allowed to name that branch. One forgotten check and a
common user could edit another branch's stock by changing a hidden form
field.

By deriving the branch from the user, the fraud is not made hard — it is
made **impossible to express**. There is no parameter to forge.
Authorisation is no longer a check that can be forgotten; it is a
property of the function's shape.

`_user_branch_id` also raises `NoBranchAssigned` when the user has no
branch (the admin, whose `branch_id` is `NULL`). It returns the value
rather than only checking it, so the control cannot be skipped: without
it, there is no `branch_id` to continue with.

## Product ID verification

Stock rows store only a `product_id`, with no foreign key, because
product data lives in an external API and never in our database. Nothing
in the schema prevents writing an invalid identifier. The verification
in the service layer is the applicative substitute for the foreign key
we cannot create.

The API is queried through `product_exists()`, on the route
`/api/v1/products/{id}` — the single-product route, not the list.
The list excludes discontinued products by default, which would wrongly
report product 32 as unknown even though we hold stock of it.
"Discontinued" is not "inexistent".

The check runs **only when a new stock row is created** — that is, when
`add_stock` finds no existing row for `(branch_id, product_id)`. This is
the only moment a non-validated identifier could enter the database.
Adding to or removing from an existing row never calls the API.

This makes the external dependency cheap and safe. If the API is down,
`product_exists` raises `ProductApiUnavailable`, and only the
referencing of a *brand-new* product is blocked. Consulting stock,
adding to an existing product, or removing stock all keep working.

## Known limitation

Product validation is **prospective**: it prevents new invalid
identifiers from entering, but does not detect identifiers already
present. Rows inserted outside the service layer — in particular the
seed data — are not covered. If the project were to last, a small audit
script listing orphan `product_id` values would be the answer. In a
two-week project this is a conscious trade-off, not an oversight.
