# API example responses

These files are **example request/response pairs** for the ClearPath lookup routes
(SPEC.md §7 and §9). They are mocks for the frontend (Person 1), not real data. Every
URL, title, excerpt, hash and form name is a placeholder in `<angle brackets>`, and
numbers such as `floor_area_sqft: 600` are arbitrary test inputs, not Irvine rules. Each
file holds `{"request", "status_code", "response"}`, and every response carries
`"example": true`, which the real API will not send. When the real API needs a different
shape, **update these files first, then the code**, and tell Person 1. Person 5 owns
the project and timeline examples.
