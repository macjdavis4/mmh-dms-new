import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { articleForPage, type HelpSummary, matchesPage } from "./api";
import { helpHref, Inline } from "./Inline";

function summary(slug: string, pages: string[], order = 100): HelpSummary {
  return { slug, title: slug, summary: "", section: "units", section_title: "Units", pages, order };
}

describe("help: inline text", () => {
  function renderInline(text: string) {
    return render(
      <MemoryRouter>
        <p data-testid="p">
          <Inline text={text} />
        </p>
      </MemoryRouter>,
    );
  }

  it("renders bold, code and links as elements", () => {
    renderInline("Press **Save**, type `WO-20001`, see [units](/units) or [quotes](help:quotes#print-the-quote).");
    expect(screen.getByText("Save").tagName).toBe("STRONG");
    expect(screen.getByText("WO-20001").tagName).toBe("CODE");
    expect(screen.getByRole("link", { name: "units" })).toHaveAttribute("href", "/units");
    expect(screen.getByRole("link", { name: "quotes" })).toHaveAttribute("href", "/help/quotes#print-the-quote");
  });

  it("never links outside the app or renders HTML", () => {
    renderInline("[bad](https://evil.example) [worse](//evil.example) <b>x</b>");
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByTestId("p").textContent).toContain("<b>x</b>");
  });

  it("maps help: links to the help pages", () => {
    expect(helpHref("help:work-orders")).toBe("/help/work-orders");
    expect(helpHref("help:work-orders#log-labor")).toBe("/help/work-orders#log-labor");
    expect(helpHref("/service")).toBe("/service");
  });
});

describe("help: the ? button finds the article for the page", () => {
  const articles = [summary("units", ["/units"]), summary("unit-page", ["/units/:id"]), summary("unit-form", ["/units/new", "/units/:id/edit"])];

  it("matches patterns", () => {
    expect(matchesPage("/units/:id", "/units/42")).toBe(true);
    expect(matchesPage("/units/:id", "/units/42/edit")).toBe(false);
    expect(matchesPage("/", "/")).toBe(true);
    expect(matchesPage("/units", "/units/")).toBe(true);
  });

  it("prefers an exact path over a pattern", () => {
    expect(articleForPage(articles, "/units/new")?.slug).toBe("unit-form");
    expect(articleForPage(articles, "/units/42")?.slug).toBe("unit-page");
    expect(articleForPage(articles, "/units/42/edit")?.slug).toBe("unit-form");
    expect(articleForPage(articles, "/units")?.slug).toBe("units");
    expect(articleForPage(articles, "/nowhere")).toBeUndefined();
  });
});
