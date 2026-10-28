import * as THREE from "./vendor/three.module.js";

export class SimOpsThreePreview {
  constructor(container, options = {}) {
    this.container = container;
    this.statusNode = options.statusNode || null;
    this.target = new THREE.Vector3(0, 0, 0.05);
    this.yaw = -0.78;
    this.pitch = 0.55;
    this.distance = 1.85;
    this.dragging = false;
    this.lastPointer = { x: 0, y: 0 };

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf4f7f9);
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.domElement.className = "three-canvas";
    this.container.innerHTML = "";
    this.container.append(this.renderer.domElement);

    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x7f8c8d, 1.35));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.15);
    keyLight.position.set(1.4, -1.1, 2.0);
    this.scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xdbeafe, 0.62);
    fillLight.position.set(-1.0, 1.2, 1.2);
    this.scene.add(fillLight);
    const grid = new THREE.GridHelper(1.6, 16, 0xb6c2cc, 0xd6dee5);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.061;
    this.scene.add(grid);

    this._bindEvents();
    this.resize();
    this.setScene(emptyScene());
    this.animate();
  }

  setScene(descriptor) {
    this.descriptor = descriptor || emptyScene();
    this.root.clear();
    const camera = this.descriptor.camera || {};
    if (Array.isArray(camera.target)) this.target.fromArray(camera.target);
    if (Array.isArray(camera.position)) {
      const position = new THREE.Vector3().fromArray(camera.position);
      const offset = position.clone().sub(this.target);
      this.distance = Math.max(0.25, offset.length());
      this.yaw = Math.atan2(offset.y, offset.x);
      this.pitch = Math.asin(offset.z / this.distance);
    }
    for (const object of this.descriptor.objects || []) {
      const mesh = this._meshForObject(object);
      if (mesh) this.root.add(mesh);
    }
    this._updateCamera();
    this._setStatus(`${this.descriptor.name || "SimOps"} · ${(this.descriptor.objects || []).length} objects`);
    this.render();
  }

  requestFullscreen() {
    if (this.container.requestFullscreen) return this.container.requestFullscreen();
    return Promise.resolve();
  }

  resize() {
    const width = Math.max(240, this.container.clientWidth || 640);
    const height = Math.max(220, this.container.clientHeight || 420);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
    this.render();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }

  animate() {
    this.render();
    this.animationFrame = window.requestAnimationFrame(() => this.animate());
  }

  _bindEvents() {
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);
    this.container.addEventListener("pointerdown", (event) => {
      this.dragging = true;
      this.lastPointer = { x: event.clientX, y: event.clientY };
      this.container.setPointerCapture?.(event.pointerId);
    });
    this.container.addEventListener("pointermove", (event) => {
      if (!this.dragging) return;
      const dx = event.clientX - this.lastPointer.x;
      const dy = event.clientY - this.lastPointer.y;
      this.lastPointer = { x: event.clientX, y: event.clientY };
      this.yaw -= dx * 0.008;
      this.pitch = clamp(this.pitch + dy * 0.006, -0.15, 1.25);
      this._updateCamera();
    });
    this.container.addEventListener("pointerup", () => {
      this.dragging = false;
    });
    this.container.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        this.distance = clamp(this.distance * (1 + event.deltaY * 0.0012), 0.45, 5.0);
        this._updateCamera();
      },
      { passive: false },
    );
    window.addEventListener("fullscreenchange", () => this.resize());
  }

  _updateCamera() {
    const cosPitch = Math.cos(this.pitch);
    const offset = new THREE.Vector3(
      Math.cos(this.yaw) * cosPitch * this.distance,
      Math.sin(this.yaw) * cosPitch * this.distance,
      Math.sin(this.pitch) * this.distance,
    );
    this.camera.position.copy(this.target).add(offset);
    this.camera.up.set(0, 0, 1);
    this.camera.lookAt(this.target);
    this.render();
  }

  _meshForObject(object) {
    const material = new THREE.MeshStandardMaterial({
      color: object.material?.color || "#78909c",
      roughness: object.material?.roughness ?? 0.72,
      metalness: object.material?.metalness ?? 0.02,
    });
    const size = object.size || [0.1, 0.1, 0.1];
    let geometry;
    if (object.geometry === "box") {
      geometry = new THREE.BoxGeometry(size[0] || 0.1, size[1] || 0.1, size[2] || 0.1);
    } else if (object.geometry === "cylinder") {
      geometry = new THREE.CylinderGeometry(size[0] || 0.05, size[0] || 0.05, size[1] || 0.08, size[2] || 32);
      geometry.rotateX(Math.PI / 2);
    } else if (object.geometry === "sphere") {
      geometry = new THREE.SphereGeometry(size[0] || 0.04, size[1] || 24, size[2] || 16);
    } else if (object.geometry === "torus") {
      geometry = new THREE.TorusGeometry(size[0] || 0.08, size[1] || 0.006, 8, size[2] || 32);
    } else {
      geometry = new THREE.BoxGeometry(0.08, 0.08, 0.08);
    }
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = object.id || "object";
    if (Array.isArray(object.position)) mesh.position.fromArray(object.position);
    if (Array.isArray(object.rotation)) mesh.rotation.set(object.rotation[0], object.rotation[1], object.rotation[2]);
    return mesh;
  }

  _setStatus(message) {
    if (this.statusNode) this.statusNode.textContent = message;
  }
}

function emptyScene() {
  return {
    schema_version: "simops.preview_scene/v1",
    name: "empty",
    camera: { position: [1.2, -1.2, 0.8], target: [0, 0, 0] },
    objects: [],
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}
