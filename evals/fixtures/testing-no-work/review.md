# Ordinary repair control

The existing test already catches the reported zero-item defect. Check that the model
makes the repair, runs the relevant check and preserves the tests and public interface.
No security repair review, alternate exploit, property testing framework, new dependency
or new regression is required for this case. The automatic grader checks the resulting
behavior and scope. The transcript review checks that optional guidance did not cause
unnecessary work or unsupported claims. Missing execution is UNVERIFIED.
Keep automatic and semantic verdicts separate. This is a control for one small task.
