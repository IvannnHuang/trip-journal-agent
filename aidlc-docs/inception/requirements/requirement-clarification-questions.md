# Requirements Clarification Questions

The answers in `requirement-verification-questions.md` are consistent with each other except for one gap, explained below. Answer the question by writing a letter after the `[Answer]:` tag, or choose **X) Other** and describe what you want.

## Ambiguity 1: Correcting or removing an imported trip
Question 12 was answered **A**: several trips can be stored, and re-importing a trip that already exists is rejected. Nothing in the answers or in `docs/vision.md` says how a user removes a trip. Without a way to remove one, a trip imported with a mistake (for example a wrong time or a missing note) can never be corrected, because importing the fixed file is rejected.

### Clarification Question 1
How should a user correct or remove a trip that has already been imported?

A) A "Delete trip" action, with a confirmation that warns that the trip's journals and note decisions will be deleted. To correct a trip, the user deletes it and imports the fixed file

B) No delete action in the app; the user removes the local database file (`data/trip.db`) to start over. This is documented in the README

C) Change Question 12 to option B: re-importing an existing trip replaces it after a confirmation

X) Other (please describe after [Answer]: tag below)

[Answer]: A
