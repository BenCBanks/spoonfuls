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
  return Object.hasOwn(screens, route) || route === "signin" || route === "signup"
    ? route
    : "cookbook";
}

function field(labelText, type, name, autocomplete, required = true) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = labelText;
  const input = document.createElement("input");
  input.type = type;
  input.name = name;
  input.autocomplete = autocomplete;
  input.required = required;
  wrapper.append(input);
  const error = document.createElement("span");
  error.className = "field-error";
  error.dataset.errorFor = name;
  wrapper.append(error);
  return wrapper;
}

function renderAuth(mode) {
  const signup = mode === "signup";
  document.title = `${signup ? "Create account" : "Sign in"} · Spoonfuls`;
  app.replaceChildren();

  const section = document.createElement("section");
  section.className = "auth-screen";
  section.setAttribute("aria-labelledby", "auth-title");

  const title = document.createElement("h1");
  title.id = "auth-title";
  title.textContent = signup ? "Create your account" : "Welcome back";
  section.append(title);

  const intro = document.createElement("p");
  intro.textContent = signup
    ? "Start your private cookbook. The first account needs the owner-provided bootstrap code."
    : "Sign in to get back to your cookbook.";
  section.append(intro);

  const form = document.createElement("form");
  form.className = "auth-form";
  form.noValidate = true;
  form.append(field("Email", "email", "email", "email"));
  form.append(field("Password", "password", "password", signup ? "new-password" : "current-password"));
  if (signup) form.append(field("Invite code (if you have one)", "text", "invite_code", "off", false));
  if (signup) form.append(field("Bootstrap code (first account only)", "text", "bootstrap_code", "off", false));

  const formError = document.createElement("p");
  formError.className = "form-error";
  formError.setAttribute("role", "alert");
  form.append(formError);

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "primary-action";
  submit.textContent = signup ? "Create account" : "Sign in";
  form.append(submit);
  section.append(form);

  const switcher = document.createElement("p");
  switcher.className = "auth-switcher";
  switcher.append(document.createTextNode(signup ? "Already have an account? " : "New to Spoonfuls? "));
  const switchLink = document.createElement("a");
  switchLink.href = signup ? "#signin" : "#signup";
  switchLink.textContent = signup ? "Sign in" : "Create an account";
  switcher.append(switchLink);
  section.append(switcher);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    formError.textContent = "";
    form.querySelectorAll(".field-error").forEach((error) => { error.textContent = ""; });
    submit.disabled = true;
    const data = Object.fromEntries(new FormData(form));
    if (!data.invite_code) delete data.invite_code;
    try {
      const response = await fetch(`/api/auth/${signup ? "signup" : "signin"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = body.detail;
        if (detail && typeof detail === "object" && detail.field) {
          const fieldError = form.querySelector(`[data-error-for="${detail.field}"]`);
          if (fieldError) fieldError.textContent = detail.message;
          else formError.textContent = detail.message;
        } else {
          formError.textContent = typeof detail === "string" ? detail : "We could not sign you in. Try again.";
        }
        return;
      }
      window.location.hash = "#cookbook";
    } catch (_error) {
      formError.textContent = "We could not reach Spoonfuls. Your details are still here; try again.";
    } finally {
      submit.disabled = false;
    }
  });
  app.append(section);
}

function renderShell(route) {
  const screen = screens[route];
  document.title = `${screen.title} · Spoonfuls`;
  app.replaceChildren();

  const header = document.createElement("div");
  header.className = "shell-header";
  const accountLink = document.createElement("a");
  accountLink.href = "#signin";
  accountLink.textContent = "Sign in";
  header.append(accountLink);
  app.append(header);

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

function render() {
  const route = currentRoute();
  if (route === "signin" || route === "signup") renderAuth(route);
  else renderShell(route);
}

window.addEventListener("hashchange", render);
render();
