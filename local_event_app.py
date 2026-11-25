import io
import os
import socket
import zipfile
import json
from pathlib import Path

import streamlit as st
from PIL import Image

from matcher import find_matches
from utils import image_bytes_preview, make_qr


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Event Photo Finder - Local HDD Mode",
    page_icon="📸",
    layout="wide"
)

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp"
}

CONFIG_FILE = Path(__file__).parent / "local_event_config.json"


# ============================================================
# CONFIG FILE
# ============================================================

def read_local_config():
    try:
        if CONFIG_FILE.exists():
            return json.loads(
                CONFIG_FILE.read_text(encoding="utf-8")
            )
    except Exception:
        pass

    return {}


def write_local_config(folder, event_name):
    try:
        CONFIG_FILE.write_text(
            json.dumps(
                {
                    "folder": folder,
                    "event_name": event_name
                },
                indent=4
            ),
            encoding="utf-8"
        )
    except Exception as e:
        st.error(f"Could not save configuration: {e}")


# ============================================================
# NETWORK
# ============================================================

def lan_ip():

    sock = None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))

        ip = sock.getsockname()[0]

        return ip

    except Exception:
        return "127.0.0.1"

    finally:
        if sock:
            sock.close()


# ============================================================
# PATH HANDLING
# ============================================================

def normalize_folder_path(folder):

    if folder is None:
        return ""

    cleaned = str(folder).strip()

    # Remove surrounding quotes
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]

    if cleaned.startswith("'") and cleaned.endswith("'"):
        cleaned = cleaned[1:-1]

    cleaned = cleaned.strip()

    # Expand Windows environment variables
    cleaned = os.path.expandvars(cleaned)

    # Expand user path
    cleaned = os.path.expanduser(cleaned)

    # Normalize separators and redundant path elements
    cleaned = os.path.normpath(cleaned)

    return cleaned


def validate_folder(folder):

    cleaned = normalize_folder_path(folder)

    if not cleaned:
        raise ValueError("Please enter a folder path.")

    # Use Windows-compatible path checks
    exists = os.path.exists(cleaned)
    is_dir = os.path.isdir(cleaned)

    if not exists:

        raise ValueError(
            "The path does not exist or cannot be accessed.\n\n"
            f"Path received:\n{cleaned}\n\n"
            "Please verify the folder path in File Explorer."
        )

    if not is_dir:

        raise ValueError(
            "The entered path exists, but it is not a folder.\n\n"
            f"Path received:\n{cleaned}"
        )

    # Test folder accessibility
    try:
        next(os.scandir(cleaned), None)

    except PermissionError:

        raise ValueError(
            "Windows denied access to this folder.\n\n"
            f"Path:\n{cleaned}\n\n"
            "Check the folder permissions."
        )

    except Exception as e:

        raise ValueError(
            f"Unable to access folder:\n{cleaned}\n\n"
            f"Details: {e}"
        )

    return cleaned


# ============================================================
# PHOTO SCANNER
# ============================================================

def load_local_gallery(folder):

    cleaned = validate_folder(folder)

    root = Path(cleaned)

    images = []

    try:

        for current_root, directories, files in os.walk(cleaned):

            # Skip inaccessible folders where possible
            directories[:] = directories

            for filename in files:

                extension = Path(filename).suffix.lower()

                if extension not in IMAGE_EXTS:
                    continue

                full_path = os.path.join(
                    current_root,
                    filename
                )

                try:

                    if not os.path.isfile(full_path):
                        continue

                    with open(full_path, "rb") as f:
                        image_data = f.read()

                    preview = image_bytes_preview(
                        image_data,
                        max_side=700
                    )

                    relative_name = os.path.relpath(
                        full_path,
                        cleaned
                    )

                    images.append(
                        {
                            "name": relative_name,
                            "original": image_data,
                            "preview": preview
                        }
                    )

                except Exception as e:

                    st.warning(
                        f"Could not load {filename}: {e}"
                    )

    except Exception as e:

        raise ValueError(
            f"Photo scanning failed.\n\n"
            f"Folder: {cleaned}\n\n"
            f"Details: {e}"
        )

    return images


# ============================================================
# PAGE MODE
# ============================================================

params = st.query_params

is_guest = params.get("mode", "") == "guest"

local_cfg = read_local_config()


# ============================================================
# ORGANIZER MODE
# ============================================================

if not is_guest:

    st.title("📸 Event Photo Finder — Local Event Setup")

    st.info(
        "This mode reads photos directly from your computer. "
        "Internal HDD, external HDD, USB drives and accessible "
        "network drives are supported. Guests must connect "
        "to the same Wi-Fi network."
    )

    folder = st.text_input(
        "Photo folder path",
        value=st.session_state.get("local_folder", ""),
        placeholder=r"C:\Users\YourName\Pictures\Wedding",
        help="Paste the complete folder path. Quotation marks are accepted."
    )

    st.session_state["local_folder"] = folder

    event_name = st.text_input(
        "Event name",
        value=st.session_state.get(
            "local_event_name",
            "Wedding Photo Gallery"
        )
    )

    st.session_state["local_event_name"] = event_name

    # --------------------------------------------------------
    # SCAN BUTTON
    # --------------------------------------------------------

    if st.button(
        "📂 Scan photo folder",
        type="primary"
    ):

        if not folder.strip():

            st.error("Please enter a folder path.")

        else:

            with st.spinner("Scanning folder and subfolders..."):

                try:

                    cleaned_folder = validate_folder(folder)

                    gallery = load_local_gallery(cleaned_folder)

                    st.session_state["local_gallery_count"] = len(gallery)

                    st.session_state["local_scan_ok"] = True

                    st.session_state["local_scan_folder"] = cleaned_folder

                    write_local_config(
                        cleaned_folder,
                        event_name
                    )

                    st.success(
                        f"Folder scanned successfully. "
                        f"{len(gallery)} supported images found."
                    )

                except Exception as e:

                    st.session_state["local_scan_ok"] = False

                    st.error(str(e))

    # --------------------------------------------------------
    # SCAN STATUS
    # --------------------------------------------------------

    if st.session_state.get("local_scan_ok"):

        st.success(
            f"Gallery ready: "
            f"{st.session_state.get('local_gallery_count', 0)} photos"
        )

    # --------------------------------------------------------
    # QR CODE
    # --------------------------------------------------------

    st.markdown("---")

    st.subheader("📺 QR code for guest access")

    ip = lan_ip()

    guest_url = f"http://{ip}:8501/?mode=guest"

    st.code(guest_url)

    qr = make_qr(guest_url)

    st.image(
        qr,
        caption="Guests can scan this QR code using their phones",
        width=420
    )

    st.markdown(
        """
        ### Display instructions

        1. Connect the laptop and guest phones to the same Wi-Fi.
        2. Move the browser to your extended TV/display.
        3. Press `F11` for full screen.
        4. Display the QR code.
        5. Keep the application running.
        """
    )

    st.warning(
        "Do not close the application or terminal while guests "
        "are searching for their photos."
    )

    st.markdown("---")

    st.subheader("Test guest page")

    st.markdown(
        f"[Open guest photo search]({guest_url})"
    )

    st.caption(
        "If Windows Firewall asks for permission, allow Python "
        "on Private networks only."
    )


# ============================================================
# GUEST MODE
# ============================================================

else:

    st.title("📸 Find Your Event Photos")

    st.caption(
        "Upload or take a selfie to find your event photos."
    )

    # --------------------------------------------------------
    # LOAD CONFIG
    # --------------------------------------------------------

    folder = local_cfg.get("folder", "")

    event_name = local_cfg.get(
        "event_name",
        "Wedding Photo Gallery"
    )

    if not folder:

        st.error(
            "The organizer has not configured the photo folder yet."
        )

        st.stop()

    # --------------------------------------------------------
    # VALIDATE CONFIGURED FOLDER
    # --------------------------------------------------------

    try:

        folder = validate_folder(folder)

    except Exception as e:

        st.error(
            "The configured photo folder is unavailable.\n\n"
            f"{e}"
        )

        st.stop()

    # --------------------------------------------------------
    # EVENT
    # --------------------------------------------------------

    st.subheader(event_name)

    st.markdown(
        "Take a selfie or upload a photo to find your pictures."
    )

    camera = st.camera_input("Take a selfie")

    uploads = st.file_uploader(
        "Or upload selfie image(s)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )

    selfies = []

    if camera:

        selfies.append(
            {
                "name": "Camera selfie",
                "bytes": camera.getvalue()
            }
        )

    if uploads:

        for uploaded_file in uploads:

            selfies.append(
                {
                    "name": uploaded_file.name,
                    "bytes": uploaded_file.getvalue()
                }
            )

    # --------------------------------------------------------
    # MATCHING THRESHOLD
    # --------------------------------------------------------

    threshold = st.slider(
        "Matching sensitivity",
        min_value=0.20,
        max_value=0.70,
        value=0.40,
        step=0.01,
        help="Lower values are stricter. Higher values may find more photos but may increase false matches."
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if selfies and st.button(
        "🔎 Find My Photos",
        type="primary",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "Loading event photos..."
            ):

                images = load_local_gallery(folder)

            if not images:

                st.error(
                    "No supported photos were found in the folder."
                )

            else:

                merged = {}

                all_errors = []

                progress = st.progress(0)

                for selfie_index, selfie in enumerate(selfies):

                    try:

                        matches, errors = find_matches(
                            selfie["bytes"],
                            images,
                            threshold
                        )

                        all_errors.extend(errors)

                        for match in matches:

                            name = match["name"]

                            if (
                                name not in merged
                                or match["distance"]
                                < merged[name]["distance"]
                            ):

                                merged[name] = match

                    except Exception as e:

                        all_errors.append(
                            f"{selfie['name']}: {e}"
                        )

                    progress.progress(
                        (selfie_index + 1) / len(selfies)
                    )

                progress.empty()

                results = sorted(
                    merged.values(),
                    key=lambda m: m["distance"]
                )

                st.session_state["local_matches"] = results

                st.session_state["local_errors"] = all_errors

                st.session_state["local_total"] = len(images)

        except Exception as e:

            st.error(
                f"Gallery search failed: {e}"
            )

    # ========================================================
    # RESULTS
    # ========================================================

    if "local_matches" in st.session_state:

        matches = st.session_state["local_matches"]

        errors = st.session_state.get(
            "local_errors",
            []
        )

        st.markdown("---")

        st.subheader("🎉 Search Results")

        st.write(
            f"Photos scanned: "
            f"{st.session_state.get('local_total', 0)}"
            f" | Matching photos: {len(matches)}"
        )

        # ----------------------------------------------------
        # NO MATCHES
        # ----------------------------------------------------

        if not matches:

            st.warning(
                "No matching photos found. "
                "Try another selfie or adjust matching sensitivity."
            )

        # ----------------------------------------------------
        # MATCHED PHOTOS
        # ----------------------------------------------------

        else:

            cols = st.columns(3)

            for i, match in enumerate(matches):

                with cols[i % 3]:

                    st.image(
                        match["preview"],
                        use_container_width=True
                    )

                    st.caption(match["name"])

                    st.caption(
                        f"Match distance: "
                        f"{match['distance']:.4f}"
                    )

                    st.download_button(
                        "⬇️ Download photo",
                        data=match["original"],
                        file_name=Path(
                            match["name"]
                        ).name,
                        mime="application/octet-stream",
                        key=f"local_download_{i}",
                        use_container_width=True
                    )

            # ------------------------------------------------
            # ZIP DOWNLOAD
            # ------------------------------------------------

            if len(matches) > 1:

                zip_buffer = io.BytesIO()

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    for match in matches:

                        zip_file.writestr(
                            match["name"],
                            match["original"]
                        )

                st.download_button(
                    "📦 Download all matching photos",
                    data=zip_buffer.getvalue(),
                    file_name="my_event_photos.zip",
                    mime="application/zip",
                    use_container_width=True
                )

        # ----------------------------------------------------
        # PROCESSING ERRORS
        # ----------------------------------------------------

        if errors:

            with st.expander(
                "Processing notes / errors"
            ):

                for error in errors[:30]:

                    st.write(error)
