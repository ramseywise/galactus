SENIOR AI ENGINEER
CHALLENGE

Distribution: Candidates
Document Owner: Julie Plusquin
GOAL
For the Senior AI Engineer challenge, we are providing you with 1 use case. We would
like to learn how you would solve this with AI. We want you to come up with a
solution and implement it. You are presenting towards the ‘lead engineers of the
Customer’.
What will the interview look like?
[keep an eye on time management!]
- [5min] Quick round table for everyone to introduce themselves
- [20min] Presentation on your design and implementation
You can choose if you’d like to create a presentation for it or use another format (website,
whiteboard, ...), we would like to see/hear how you approached it in a digestible format. If you
decide to present slides, make sure to keep it limited to 10 slides.
- [25min] Q&A
- [10min] Questions from your side
Case - Automated Generative Marketing Collateral
Customer C is a marketing automation agency that creates personalized B2B
marketing materials (like physical newsletters and brochures). Currently, this process
is highly manual, tedious, and difficult to scale. When a 'Sender' (e.g., an AI software
vendor) wants to target a 'Receiver' (e.g., a large logistics company), human editors
perform the following steps manually:
● Research: Visit both companies' websites to understand the Sender's
offerings and the Receiver's industry challenges.
● Content Creation: Write custom articles from scratch that bridge these two
domains, ensuring the tone is appropriate and the narrative makes sense for a
B2B pitch.

Copyright © 2026 ML6. All rights reserved. ML6 Public Information | 1

● Asset Gathering: Manually source relevant visuals, such as extracting
company logos or finding contextually appropriate images.
● Layout Formatting: Meticulously copy-paste all this gathered text and
imagery into strict, pre-defined publishing templates. This often involves trial
and error to ensure the text fits perfectly within column limits, font sizes are
adhered to, and no awkward white space is left behind.
They want to fully automate this pipeline using Generative AI. The desired system
should take as input context PDFs on both the sender and receiver company and
use an LLM to generate tailored, factually correct articles. The input PDFs contain
text, images and tables. Finally, the system must output a JSON that maps the
generated text into a pre-defined layout template while respecting specific
constraints (e.g., word limits, image placeholders, and theme colors).
YOUR TASK:
Design a technical solution to this challenge. Your design must contain the
orchestration of the contextual data retrieval, LLM interaction and layout
formatting. It must also contain a cloud architecture for either AWS, GCP or Azure.
Implement:
Build a lightweight prototype backend. Your prototype must expose two endpoints:
- An endpoint to upload PDFs as context for a certain sender and receiver
company.
- An endpoint to generate a short, tailored article as a structured JSON based
on a prompt for a certain sender and receiver company.
Deliverable:
- Code Submission: please upload your code to a private GitHub repository.
After the challenge we might ask you to share your code with your
interviewers. You don’t need to share the code before the interview.
- You will walk the lead engineers of the Customer through your solution.
Note: The use of AI tools for implementation is highly encouraged. However, you
should be prepared to discuss and demonstrate a thorough understanding of your
solution during the interview.
