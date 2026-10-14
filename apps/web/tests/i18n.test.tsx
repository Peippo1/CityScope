import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { LocaleProvider, SUPPORTED_LOCALES, useLocale } from "../lib/i18n";

function Harness() {
  const { locale, setLocale, copy } = useLocale();
  return <><select aria-label="Language" value={locale} onChange={(event) => setLocale(event.target.value as typeof locale)}>{SUPPORTED_LOCALES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select><span>{copy.planRoute}</span></>;
}

describe("locale support", () => {
  it("offers the supported launch languages", () => {
    expect(SUPPORTED_LOCALES.map((item) => item.id)).toEqual(["en-GB", "fr-FR", "es-ES", "it-IT"]);
  });

  it("persists a manual language choice for the next visit", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    const view = render(<LocaleProvider><Harness /></LocaleProvider>);
    await user.selectOptions(screen.getByRole("combobox", { name: "Language" }), "fr-FR");
    expect(screen.getByText("Planifier mon trajet")).toBeVisible();
    expect(window.localStorage.getItem("cityscope-locale")).toBe("fr-FR");
    view.unmount();
    render(<LocaleProvider><Harness /></LocaleProvider>);
    expect(await screen.findByText("Planifier mon trajet")).toBeVisible();
  });
});
