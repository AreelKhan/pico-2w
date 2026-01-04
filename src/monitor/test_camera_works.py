import cv2
import time

import argparse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--device", type=int, default=0)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--format", choices=["MJPG", "YUYV"], default="MJPG")
    p.add_argument("--grab-only", action="store_true")
    p.add_argument("--auto-exposure", choices=["auto", "manual"], default=None)
    p.add_argument("--exposure", type=float, default=None)
    p.add_argument("--gain", type=float, default=None)
    p.add_argument("--no-display", action="store_true")
    p.add_argument("--no-overlay", action="store_true")
    p.add_argument("--duration-s", type=float, default=0.0)
    return p.parse_args()


def fourcc_to_str(fourcc: float) -> str:
    v = int(fourcc)
    return "".join([chr((v >> (8 * i)) & 0xFF) for i in range(4)])


def main() -> None:
    args = parse_args()

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, getattr(cv2, "VideoWriter_fourcc")(*args.format))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    if args.auto_exposure is not None and hasattr(cv2, "CAP_PROP_AUTO_EXPOSURE"):
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if args.auto_exposure == "auto" else 0.25)
    if args.exposure is not None:
        cap.set(cv2.CAP_PROP_EXPOSURE, args.exposure)
    if args.gain is not None:
        cap.set(cv2.CAP_PROP_GAIN, args.gain)

    print("Actual width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print("Actual height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("Requested fps:", args.fps)
    print("Reported fps:", cap.get(cv2.CAP_PROP_FPS))
    print("Reported fourcc:", fourcc_to_str(cap.get(cv2.CAP_PROP_FOURCC)))
    if hasattr(cv2, "CAP_PROP_AUTO_EXPOSURE"):
        print("Auto exposure:", cap.get(cv2.CAP_PROP_AUTO_EXPOSURE))
    print("Exposure:", cap.get(cv2.CAP_PROP_EXPOSURE))
    print("Gain:", cap.get(cv2.CAP_PROP_GAIN))
    print("Mode:", "grab-only" if args.grab_only else "read(decode)")

    last_time = time.time()
    frame_count = 0
    fps = 0.0
    start = time.time()

    if not args.no_display:
        print("Press q to quit")

    while True:
        if args.grab_only:
            ret = cap.grab()
            frame = None
        else:
            ret, frame = cap.read()

        if not ret:
            print("Frame read failed")
            continue

        frame_count += 1
        now = time.time()
        if now - last_time >= 1.0:
            fps = frame_count / (now - last_time)
            frame_count = 0
            last_time = now
            print(f"FPS: {fps:.1f}")

        if args.duration_s > 0 and (now - start) >= args.duration_s:
            break

        if not args.no_display and frame is not None:
            if not args.no_overlay:
                cv2.putText(
                    frame,
                    f"FPS: {fps:.1f}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                )

            cv2.imshow("Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if not args.no_display:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
