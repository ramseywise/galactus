// Registers jest-dom's custom matchers (toBeInTheDocument, toHaveTextContent,
// …) with vitest's expect. Loaded via vitest.config.ts's setupFiles, so no test
// file needs to import it.
import "@testing-library/jest-dom/vitest";
