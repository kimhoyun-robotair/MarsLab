const benchmarkData = {
  base: {
    summary: "LiDAR remains sub-metre while RGB degrades 7.9× under dense dust.",
    metrics: [
      ["ORB-SLAM", "RGB · τ 0.5", 0.59],
      ["ORB-SLAM", "RGB · τ 6.0", 4.7],
      ["RTAB-Map", "RGB-D + Odom · τ 0.5", 0.48],
      ["RTAB-Map", "RGB-D + Odom · τ 6.0", 0.64],
      ["MOLA", "LiDAR · nominal", 0.2],
    ],
  },
  crater: {
    summary: "Self-similar rocky terrain breaks monocular tracking under dense dust.",
    metrics: [
      ["ORB-SLAM", "RGB · τ 0.5", 40.28],
      ["ORB-SLAM", "RGB · τ 6.0", null],
      ["RTAB-Map", "RGB-D + Odom · τ 0.5", 8.84],
      ["RTAB-Map", "RGB-D + Odom · τ 6.0", 10.61],
      ["MOLA", "LiDAR · nominal", 0.13],
    ],
  },
  canyon: {
    summary: "Both monocular runs lose tracking; LiDAR closes 648 m with 0.38 m ATE.",
    metrics: [
      ["ORB-SLAM", "RGB · τ 0.5", null],
      ["ORB-SLAM", "RGB · τ 6.0", null],
      ["RTAB-Map", "RGB-D + Odom · τ 0.5", 12.28],
      ["RTAB-Map", "RGB-D + Odom · τ 6.0", 19.08],
      ["MOLA", "LiDAR · nominal", 0.38],
    ],
  },
};

const benchmarkTabs = [...document.querySelectorAll("[data-benchmark-scene]")];
const metricList = document.querySelector("#metric-list");

document.querySelector("#year").textContent = new Date().getFullYear();

function handleTabKeys(event, tabs) {
  const currentIndex = tabs.indexOf(event.currentTarget);
  let nextIndex = currentIndex;
  if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (currentIndex + 1) % tabs.length;
  if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = tabs.length - 1;
  if (nextIndex === currentIndex) return;
  event.preventDefault();
  tabs[nextIndex].focus();
  tabs[nextIndex].click();
}

function renderMetrics(scene) {
  const data = benchmarkData[scene];
  const values = data.metrics.map((metric) => metric[2]).filter((value) => value !== null);
  const maximum = Math.max(...values);
  document.querySelector("#benchmark-summary").textContent = data.summary;
  metricList.replaceChildren(
    ...data.metrics.map(([method, modality, value]) => {
      const row = document.createElement("div");
      row.className = `metric-row${value === null ? " is-failed" : ""}`;

      const name = document.createElement("div");
      name.className = "metric-name";
      name.append(method);
      const detail = document.createElement("span");
      detail.textContent = modality;
      name.append(detail);

      const metricValue = document.createElement("div");
      metricValue.className = "metric-value";
      metricValue.textContent = value === null ? "Tracking lost" : `${value.toFixed(2)} m`;

      const track = document.createElement("div");
      track.className = "metric-track";
      const fill = document.createElement("span");
      fill.style.setProperty("--metric-scale", value === null ? "0" : String(Math.max(0.03, value / maximum)));
      track.append(fill);
      row.append(name, metricValue, track);
      return row;
    }),
  );
}

function selectBenchmark(tab) {
  benchmarkTabs.forEach((item) => {
    const selected = item === tab;
    item.setAttribute("aria-selected", String(selected));
    item.tabIndex = selected ? 0 : -1;
  });
  document.querySelector("#benchmark-panel").setAttribute("aria-labelledby", tab.id);
  renderMetrics(tab.dataset.benchmarkScene);
}

benchmarkTabs.forEach((tab) => {
  tab.addEventListener("click", () => selectBenchmark(tab));
  tab.addEventListener("keydown", (event) => handleTabKeys(event, benchmarkTabs));
});

renderMetrics("base");

const sectionObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting || !entry.target.id) return;
      document.querySelectorAll("nav a").forEach((link) => {
        link.toggleAttribute("aria-current", link.getAttribute("href") === `#${entry.target.id}`);
      });
    });
  },
  { rootMargin: "-35% 0px -55%", threshold: 0 },
);

document.querySelectorAll("main section[id]").forEach((section) => sectionObserver.observe(section));

const videoPreview = document.querySelector(".video-preview");
videoPreview?.addEventListener("click", (event) => {
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  const player = document.createElement("iframe");
  player.src = "https://www.youtube-nocookie.com/embed/gkr9NTTGlTw?autoplay=1&playsinline=1";
  player.title = "MarsLab paper explanation video — YouTube";
  player.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
  player.allowFullscreen = true;
  player.referrerPolicy = "strict-origin-when-cross-origin";
  videoPreview.replaceWith(player);
  player.focus();
});

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const showcaseObserver = new IntersectionObserver((entries) => {
  entries.forEach(({target: video, isIntersecting}) => {
    if (isIntersecting) {
      if (!video.getAttribute("src")) video.src = `${video.dataset.src}?v=crop-1`;
      if (!reducedMotion.matches && !video.dataset.userPaused) video.play().catch(() => {});
    } else if (!video.paused) {
      video.dataset.observerPaused = "1";
      video.pause();
    }
  });
}, {threshold: 0.15});
document.querySelectorAll(".showcase-video").forEach((video) => {
  video.addEventListener("pause", () => {
    if (!video.dataset.observerPaused) video.dataset.userPaused = "1";
    delete video.dataset.observerPaused;
  });
  video.addEventListener("play", () => { delete video.dataset.userPaused; delete video.dataset.observerPaused; });
  showcaseObserver.observe(video);
});
window.addEventListener("message", (event) => {
  const frame = document.querySelector(".interactive-lab");
  if (event.origin !== location.origin || event.source !== frame?.contentWindow) return;
  if (event.data?.type === "marslab-demo-height" && Number.isFinite(event.data.height)) {
    frame.style.height = `${Math.max(600, Math.min(2400, event.data.height))}px`;
  }
});

const dustClip = document.querySelector('.showcase-video[data-src$="dust.mp4"]');
dustClip.addEventListener("timeupdate", () => {
  const tau = 0.3 + 5.7 * Math.min(dustClip.currentTime / (359 / 30), 1);
  document.querySelector("#showcase-tau").textContent = `τ = ${tau.toFixed(2)}`;
});
