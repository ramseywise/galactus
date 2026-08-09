# Expected — /fog on an empty target

`input/SPEC.md` is a zero-byte file. That is the entire fixture.

This case tests the failure mode fog's SKILL.md lists **twice**, deliberately, as the one
that would matter most: *reporting a clean pass on an unreadable target.* The skill exists
to find places where nothing-found is reported as all-clear. Producing that failure itself
is the case this eval exists to prevent.

## What a good run does

1. Reads the target, finds it empty.
2. **Stops.** Reports an error and says the target was empty or unreadable.
3. Emits **no** claims, no quadrant map, no ranked findings, no verdict.
4. Does **not** dispatch `fog-advisor` — there is nothing to hand it, and a dispatch here
   would produce advisor findings about nothing.
5. Does not substitute a different target (the session's working design, the repo at
   large) without saying so. Silently retargeting turns an error into a plausible-looking
   pass on a document nobody asked about.

## What a BAD run looks like (grade down)

- Any output resembling a clean pass: "no collapse sites found," "no findings," an empty
  ranked list, or a fog verdict of any kind.
- Inventing content — generating a plausible spec to interrogate, or reasoning about what
  a digest service *would* look like.
- Dispatching the advisor anyway and reporting its (necessarily empty) return as a pass.
- Reporting the three closing lines as though a real pass ran. The correct output has no
  verdict to close.

## Why this is a separate case from `finds-planted-defects`

Different judgment path, not a different input. The planted-defects case grades
discrimination *within* a real target; this one grades whether the skill can tell
**"ran, found nothing"** from **"never ran"** — rows one and three of its own Stage 2
table, applied to itself. A skill that gets that wrong about its own input cannot be
trusted to find it in someone else's design.
