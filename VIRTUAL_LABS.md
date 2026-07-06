# Virtual 3D Science Labs Simulator Documentation

This document explains the technical implementation of the 3D Virtual Science Labs built in the Vyomanta LMS frontend. It covers the current architecture, mathematical solvers, rendering patterns, and provides detailed guides for implementing and extending the Chemistry and Biology experiments.

---

## 🏗️ 1. Technical Architecture

The Virtual Labs are built on top of a client-side WebGL stack integrated directly into Next.js App Router:
*   **Core Graphics**: Vanilla **Three.js** utilizing rendering loops, perspective cameras, orbital controllers, and material geometries.
*   **Controls**: **OrbitControls** for 3D rotation, panning, and zoom limits.
*   **Layout**: Split-pane responsive CSS layout where the parameters panel is managed by React state, and the WebGL canvas runs inside a React `useEffect` hook.
*   **Performance Optimization (No-SSR)**: Three.js and xterm require client-side globals (`window`, `document`). They are lazily loaded with Next.js dynamic imports (`ssr: false`) to prevent page build crashes.

---

## 🧲 2. Physics Experiments Implementation

### A. Simple Pendulum Lab
*   **Variables**: length $L$, mass $M$, gravity $g$, damping coefficient $c$.
*   **Physics Solver**:
    The motion of a simple pendulum with air resistance is governed by the second-order differential equation:
    $$\frac{d^2\theta}{dt^2} + \frac{g}{L}\sin\theta + c\frac{d\theta}{dt} = 0$$
    Implemented using **Euler-Maruyama integration** on every frame:
    ```javascript
    const accel = -(g / L) * Math.sin(angle) - damping * velocity;
    velocity += accel * dt;
    angle += velocity * dt;
    ```
*   **3D Elements**:
    *   Bob: `THREE.SphereGeometry` with standard metallic red material.
    *   String: `THREE.Line` updating points dynamically: $x = L\sin\theta$, $y = y_{\text{pivot}} - L\cos\theta$.
    *   Forces: `THREE.ArrowHelper` indicators showing tangent Velocity Vector (Green) and Gravitational/Tension Acceleration Vector (Red).

### B. Projectile Motion Lab
*   **Variables**: launch speed $v$, launch angle $\theta$, gravity $g$.
*   **Physics Solver**:
    Kinematic equations for coordinate displacement:
    $$x(t) = v \cos\theta \cdot t$$
    $$y(t) = y_{\text{muzzle}} + v \sin\theta \cdot t - \frac{1}{2}g t^2$$
    Flight duration $T_{\text{flight}} = \frac{2v\sin\theta}{g}$.
*   **3D Elements**:
    *   Cannon barrel: `THREE.CylinderGeometry` rotated around the Z-axis by $\theta$.
    *   Projectile: `THREE.SphereGeometry` updated over elapsed time $t$.
    *   Trail: `THREE.Line` geometry populated with pre-calculated parabolic points using $T_{\text{flight}}$.

### C. Refraction & Reflection (Optics)
*   **Variables**: incident angle $\theta_1$, refractive index 1 $n_1$, refractive index 2 $n_2$.
*   **Physics Solver**:
    *   Reflected beam angle equals incident angle ($\theta_{\text{refl}} = \theta_1$).
    *   Refracted beam angle computed using **Snell's Law**:
        $$\sin\theta_2 = \frac{n_1 \sin\theta_1}{n_2}$$
    *   **Total Internal Reflection (TIR)** occurs if $\sin\theta_2 > 1.0$. The refracted light ray is extinguished, and only the reflected ray is rendered.
*   **3D Elements**:
    *   Split-medium representation: Transparent boxes representing different density layers.
    *   Beams: Cylinders representing lasers (Red for Incident, Gold for Reflected, Green for Refracted).

### D. Spring-Mass System
*   **Variables**: spring stiffness $k$, mass $M$, damping $c$.
*   **Physics Solver**:
    Governed by Hooke's Law and mass-spring-damper dynamics:
    $$\frac{d^2y}{dt^2} + \frac{c}{M}\frac{dy}{dt} + \frac{k}{M}y = 0$$
*   **3D Elements**:
    *   Spring: Helix curve rendered with `THREE.TubeGeometry`. To optimize performance, the helix height is scaled dynamically along the Y-axis inside the animation loop to represent stretch/compression.
    *   Mass: Heavy metallic box mesh linked to the bottom of the spring.

### E. Ohm's Law Circuit
*   **Variables**: voltage $V$, resistance $R$.
*   **Physics Solver**:
    Current computed via Ohm's Law: $I = \frac{V}{R}$.
*   **3D Elements**:
    *   Circuit board: Battery cylinder, resistor cylinder, and path wires (`THREE.LineSegments`).
    *   Electrons: Glowing yellow spheres translating along a pre-defined path coordinate array:
        $$\text{Speed} \propto I$$

---

## 🧪 3. Proposed Chemistry Experiments

Here is the implementation blueprint to develop the Chemistry Lab simulations:

### A. Atomic Structure Bohr Builder
*   **Concept**: Allow students to assemble Bohr models of elements by adding protons, neutrons, and electrons.
*   **Physics Math**:
    *   Protons ($Z$) determine the element name.
    *   Concentric electron shell limits: $2n^2$ (Shell 1: 2, Shell 2: 8, Shell 3: 18).
*   **Three.js Visual Implementation**:
    *   **Nucleus**: Render a cluster of red (protons) and blue (neutrons) spheres using random coordinates within a small bounding sphere radius:
        ```javascript
        const pos = new THREE.Vector3().setFromSphericalCoords(
          Math.random() * radius,
          Math.random() * Math.PI,
          Math.random() * Math.PI * 2
        );
        ```
    *   **Electron Orbits**: Render semi-transparent circular rings.
    *   **Electrons**: Small yellow spheres rotating along the orbit rings:
        $$\theta_t = \theta_0 + \omega \cdot t$$
    *   **Emission/Absorption**: Trigger particle effects (outgoing glowing photons) when the student changes the energy levels of electrons.

### B. Acid-Base Titration Lab
*   **Concept**: Titrating an acid (HCl) with a base (NaOH) using phenolphthalein indicator.
*   **Chemistry Solver**:
    *   Compute moles of $H^+$ and $OH^-$ based on buret drops:
        $$pH = -\log_{10}[H^+]$$
    *   Color transition: At equivalence point ($pH \approx 8.2$ to $10$), transition the flask liquid color from transparent `#ffffff` to pink `#FFB7D5`.
*   **Three.js Visual Implementation**:
    *   **Buret**: Draw a transparent thin cylinder with graduation marks and a stopcock valve model.
    *   **Flask**: Draw a conical container (`THREE.CylinderGeometry` with top radius < bottom radius).
    *   **Liquid mesh**: A cylinder inside the flask. As liquid volume increases, scale the height of the cylinder:
        ```javascript
        liquidMesh.scale.y = currentVolume / maxVolume;
        liquidMesh.position.y = basePosition + (liquidHeight / 2) * liquidMesh.scale.y;
        ```
    *   **Color Transition**: Interpolate color values dynamically based on $pH$:
        ```javascript
        const liquidColor = new THREE.Color('#ffffff'); // colorless
        if (pH > 8.2) {
          const t = Math.min(1, (pH - 8.2) / 1.8);
          liquidColor.lerp(new THREE.Color('#ff007f'), t); // pink
        }
        liquidMaterial.color.copy(liquidColor);
        ```

---

## 🧬 4. Proposed Biology Experiments

Here is the implementation blueprint to develop the Biology Lab simulations:

### A. 3D Animal Cell Organelles Explorer
*   **Concept**: Zoom and click to explore organelles in a eukaryotic cell.
*   **Three.js Visual Implementation**:
    *   **Cell Membrane**: Outer transparent sphere (`opacity: 0.15`).
    *   **Nucleus & Nucleolus**: Concentric inner spheres.
    *   **Mitochondria**: Bean-shaped geometry generated via a custom curve or loaded via a `.gltf` model.
    *   **Interaction (Raycaster)**: Use `THREE.Raycaster` to detect cursor clicks on organelles:
        ```javascript
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();

        window.addEventListener('click', (e) => {
          mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
          mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
          raycaster.setFromCamera(mouse, camera);
          
          const intersects = raycaster.intersectObjects(cellOrganelles);
          if (intersects.length > 0) {
            const selectedOrganelle = intersects[0].object;
            displayInfoBox(selectedOrganelle.name);
          }
        });
        ```

### B. DNA Double Helix Replication
*   **Concept**: Unzipping a DNA strand and matching base pairs (Adenine-Thymine, Cytosine-Guanine).
*   **Three.js Visual Implementation**:
    *   **Helical Strands**: Create two parallel helical tubes.
        $$\text{Strand 1}: x = R\cos\theta, z = R\sin\theta, y = \theta$$
        $$\text{Strand 2}: x = -R\cos\theta, z = -R\sin\theta, y = \theta$$
    *   **Base Pairs**: Render horizontal bars linking the strands, colored by base types:
        *   Adenine (Red) ↔ Thymine (Blue)
        *   Cytosine (Green) ↔ Guanine (Yellow)
    *   **Replication Animation**:
        *   Animate a Helicase slider along the Y-axis.
        *   As the slider moves, separate the two strands ($R \to 2R$) and split the connecting base pair cylinders into two halves.
        *   Animate incoming free nucleotides matching to the separated strands.
