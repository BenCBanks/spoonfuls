const screens = {
  cookbook: {
    title: "Cookbook",
    message: "Your recipes will live here.",
  },
  following: {
    title: "Following",
    message: "Recipes from cooks you follow will appear here.",
  },
  plan: {
    title: "Plan",
    message: "Plan a week of cooking when you are ready.",
  },
  list: {
    title: "List",
    message: "Ingredients you need will appear here.",
  },
};

const app = document.querySelector("#app");
const links = [...document.querySelectorAll("[data-route]")];

function currentRoute() {
  const route = window.location.hash.slice(1).toLowerCase();
  return Object.hasOwn(screens, route) ? route : "cookbook";
}

function render() {
  const route = currentRoute();
  const screen = screens[route];
  document.title = `${screen.title} · Spoonfuls`;
  app.replaceChildren();

  const section = document.createElement("section");
  section.className = "empty-screen";
  section.setAttribute("aria-labelledby", "screen-title");

  const title = document.createElement("h1");
  title.id = "screen-title";
  title.textContent = screen.title;
  section.append(title);

  const message = document.createElement("p");
  message.textContent = screen.message;
  section.append(message);
  app.append(section);

  links.forEach((link) => {
    const selected = link.dataset.route === route;
    link.classList.toggle("selected", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

window.addEventListener("hashchange", render);
render();
