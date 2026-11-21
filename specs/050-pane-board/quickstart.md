# Pane Board quickstart

Use these six scenes to verify Board as each phase becomes available. For repeatable snapshots, use fixed Team names, model aliases, task text, clock, and width. Start each scene with fresh Board state and a wide enough pane for untruncated rows. Compare the complete rendered Board to a fixture, including labels, spaces, selection glyphs, and blank lines. The blocks below preserve the exact reference lines in the spec. Use its section and formatting rules to complete each fixture. Run the relevant live spike separately where a scene depends on host behavior [unverified]. See `spec.md:130`–`:134`, `spec.md:158`–`:163`, and `spec.md:169`.

## 1. CoS question from a marker — Phase 2

1. Complete the current CoS turn with this line and put selection on the resulting Item.

   ```text
   [board:needs-you] Merge parser fix to main?
   ```

2. Check NEEDS YOU has one Item and the selected question reads exactly as follows.

   ```text
   ▸ 1 Merge parser fix to main?
   ```

3. Press Enter. Check title, context, source, age, quick keys `1 yes   2 no   3 hold`, reply box, and recent sent replies. Press Escape to close it. Reopen, submit a test reply to the current CoS, and confirm the Item leaves after submission. Repeat with explicit marker options and verify that they replace the default keys. Capture the hook or call trace to confirm the marker post causes zero extra model calls.

Source: `spec.md:63`–`:76`.

## 2. Dead delegate — Phase 1

1. Feed Board one `luna` delegate with task `scan docs` and a died event at a fixed time. Advance the clock by two minutes and render its open Team.
2. Check TROUBLE has count 1 and the row reads as follows.

   ```text
     ▲ luna    scan docs     died 2m ago
   ```

3. Select the row and use the footer's transcript action. Then use the dismiss action and refresh the same session. Confirm the row stays absent. Repeat with host status `killed` and check it appears in TROUBLE until dismissed.

Source: `spec.md:32`, `spec.md:50`, `spec.md:54`–`:55`.

## 3. Operator hold — Phase 1

1. Supply a `sonnet` delegate held for operator input or approval with the question `run migration?`. Use the S3 signal confirmed on the target host [unverified].
2. Check NEEDS YOU has count 1 and contains this line.

   ```text
     1 sonnet waits: run migration?
   ```

3. Repeat with an idle delegate, a background-work wait, and a Worker Question addressed to the Lead. Confirm these cases do not create an operator-hold Item.

Source: `spec.md:51`, `spec.md:142`, `spec.md:202`.

## 4. Quota pause — Phase 1

1. Supply a `haiku` delegate paused for quota, with the fixture's local reset time set to `14:20`. Start with Board closed and no other signals.
2. Check Board opens without taking chat focus [unverified live]. NEEDS YOU has count 1 and contains this line.

   ```text
     1 haiku paused: quota, resets 14:20
   ```

3. Check the pause appears without CoS text, a model call, or signals outside Board.

Source: `spec.md:52`, `spec.md:56`, `spec.md:142`, `spec.md:194`.

## 5. Secretary extraction — Phase 4

1. Complete a CoS turn containing `Merge parser fix to main?` and no markers. Supply a deterministic Secretary response for that NEEDS YOU Item with the exact source quote.
2. Check NEEDS YOU has count 1 and the row contains a dim `auto` tag as shown.

   ```text
     1 Merge parser fix to main?  auto
   ```

3. Repeat with an absent quote and confirm the Item is dropped. Repeat with a failed Secretary and with the none setting. In both cases check for `CoS turn unread, open chat`. Feed a mechanical death event and confirm that the Secretary receives no input for it. Use the Phase 4 bench separately to assess a configured model.

Source: `spec.md:99`–`:110`, `spec.md:135`–`:141`.

## 6. Folded Teams — Phase 3

1. From a Board with its own Team open, supply `ainc2` with one NEEDS YOU Item and three working delegates, and `quadmesh` with two working delegates. Use a fixed order for the Team fixture.
2. Check that two blank lines follow the open Team and these two lines appear without an intervening heading.

   ```text
   ! ainc2       1 needs you · 3 working
   ● quadmesh    2 working
   ```

3. Open a Board in each session and verify the same Team data, with each Board opening its own Team. For the live check [unverified], send a test message to another Team's delegate and check that Team's CoS receives an FYI. With a running dispatch Worker, verify the Memo is pending until the authorized checkpoint or next governed resume.

Source: `spec.md:82`–`:93`, `spec.md:175`.
