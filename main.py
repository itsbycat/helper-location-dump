import json
import math
import time
from pathlib import Path


def calculate_distance(pos1, pos2):
    """Calculate 3D Euclidean distance between two positions."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))


def calculate_angle_difference(angle1, angle2):
    """Calculate the difference between two viewangles (pitch, yaw)."""

    # Normalize angles to [-180, 180] range
    def normalize_angle(angle: int) -> int:
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle

    pitch_diff = abs(normalize_angle(angle1[0] - angle2[0]))
    yaw_diff = abs(normalize_angle(angle1[1] - angle2[1]))

    # Handle wraparound for yaw (e.g., 179 and -179 are only 2 degrees apart)
    if yaw_diff > 180:
        yaw_diff = 360 - yaw_diff

    return math.sqrt(pitch_diff**2 + yaw_diff**2)


def is_similar_lineup(max_pos, max_angle, lineup1, lineup2):
    """
    Check if two lineups are similar based on position and viewangle.

    Args:
        max_pos: Maximum distance between positions to consider them similar (units)
        max_angle: Maximum angle difference to consider them similar (degrees)
        lineup1: First lineup dictionary to compare
        lineup2: Second lineup dictionary to compare

    Returns:
        bool: True if lineups are considered similar (duplicates)
    """
    # Check if positions exist
    if "position" not in lineup1 or "position" not in lineup2:
        return False

    # Check if viewangles exist
    if "viewangles" not in lineup1 or "viewangles" not in lineup2:
        return False

    # Calculate position distance
    pos_distance = calculate_distance(lineup1["position"], lineup2["position"])

    # Calculate viewangle difference
    angle_diff = calculate_angle_difference(
        lineup1["viewangles"], lineup2["viewangles"]
    )

    # Consider similar if both position and angle are within thresholds
    return pos_distance <= max_pos and angle_diff <= max_angle


def merge_lineups(max_pos, max_angle, existing_lineups, new_lineups):
    """
    Merge new lineups into existing ones, avoiding duplicates.

    Args:
        max_pos: Maximum distance between positions to consider them similar (units)
        max_angle: Maximum angle difference to consider them similar (degrees)
        existing_lineups: List of existing lineups to merge into
        new_lineups: List of new lineups to add

    Returns:
        list: Updated list of lineups with duplicates removed
    """
    result = existing_lineups.copy()
    lineups_added = 0
    duplicates_skipped = 0

    for new_lineup in new_lineups:
        is_duplicate = False

        # Check against all existing lineups
        for existing_lineup in result:
            if is_similar_lineup(
                max_pos, max_angle, new_lineup, existing_lineup
            ):
                is_duplicate = True
                duplicates_skipped += 1
                break

        # If not a duplicate, add it
        if not is_duplicate:
            result.append(new_lineup)
            lineups_added += 1

    # print(f"    Added: {lineups_added} new lineups, Skipped: {duplicates_skipped} duplicates")
    return result


def combine_json_files(max_pos, max_angle, locs_folder, output_file):
    """
    Combine all JSON files in the locs folder into one mega JSON file.

    Args:
        max_pos: Maximum distance between positions to consider them similar (units)
        max_angle: Maximum angle difference to consider them similar (degrees)
        locs_folder: Path to the folder containing JSON files
        output_file: Name of the output mega JSON file

    Returns:
        None: Creates the output file and prints statistics
    """
    start_time = time.time()
    print("Starting to combine JSON files...")

    # Initialize the combined data structure
    combined_data = {}

    # Get all JSON files in the locs folder
    locs_path = Path(locs_folder)
    if not locs_path.exists():
        print(f"Error: {locs_folder} folder not found!")
        return

    json_files = list(locs_path.glob("*.json"))
    print(f"Found {len(json_files)} JSON files to process")

    total_lineups_processed = 0
    total_lineups_added = 0
    files_processed = 0

    # Process each JSON file
    for json_file in json_files:
        file_start_time = time.time()
        print(f"\nProcessing: {json_file.name}")

        try:
            with open(json_file, "r", encoding="utf-8") as file_handle:
                file_data = json.load(file_handle)

            file_lineup_count = 0
            # Process each map in the current file
            for map_name, lineups in file_data.items():
                if not isinstance(lineups, list):
                    print(f"  Warning: {map_name} is not a list, skipping...")
                    continue

                print(f"  Map: {map_name} - {len(lineups)} lineups")
                total_lineups_processed += len(lineups)
                file_lineup_count += len(lineups)

                # Initialize map in combined_data if it doesn't exist
                if map_name not in combined_data:
                    combined_data[map_name] = []

                # Merge lineups, avoiding duplicates
                original_count = len(combined_data[map_name])
                combined_data[map_name] = merge_lineups(
                    max_pos, max_angle, combined_data[map_name], lineups
                )
                added_this_map = len(combined_data[map_name]) - original_count
                total_lineups_added += added_this_map

            files_processed += 1
            file_time = time.time() - file_start_time
            if file_lineup_count > 0:
                lineups_per_sec = file_lineup_count / file_time if file_time > 0 else 0
                print(
                    f"  Processed {file_lineup_count} lineups in {file_time:.3f}s ({lineups_per_sec:.3f} lineups/sec)"
                )

        except json.JSONDecodeError as e:
            print(f"  Error reading {json_file.name}: {e}")
        except Exception as e:
            print(f"  Unexpected error processing {json_file.name}: {e}")

    processing_time = time.time() - start_time

    # Remove empty maps before saving
    cleanup_start = time.time()
    maps_before_cleanup = len(combined_data)
    combined_data = {
        map_name: lineups for map_name, lineups in combined_data.items() if lineups
    }
    maps_after_cleanup = len(combined_data)
    empty_maps_removed = maps_before_cleanup - maps_after_cleanup
    cleanup_time = time.time() - cleanup_start

    # Save the mega JSON file
    save_start = time.time()
    try:
        with open(output_file, "w", encoding="utf-8") as output_handle:
            json.dump(
                combined_data,
                output_handle,
                indent=4,
                ensure_ascii=False,
                sort_keys=True,
            )
        save_time = time.time() - save_start

        total_time = time.time() - start_time

        print(f"\nSuccessfully created {output_file}!")
        print("Statistics:")
        print(f"  - Total lineups processed: {total_lineups_processed}")
        print(f"  - Total lineups added: {total_lineups_added}")
        print(
            f"  - Duplicates removed: {total_lineups_processed - total_lineups_added}"
        )
        print(f"  - Maps with lineups: {len(combined_data)}")
        print(f"  - Files processed: {files_processed}")
        if empty_maps_removed > 0:
            print(f"  - Empty maps removed: {empty_maps_removed}")

        # Performance statistics
        print("\nPerformance Statistics:")
        print(f"  - Total processing time: {total_time:.3f} seconds")
        print(f"  - Data processing time: {processing_time:.3f} seconds")
        print(f"  - Cleanup time: {cleanup_time:.3f} seconds")
        print(f"  - File save time: {save_time:.3f} seconds")

        if total_lineups_processed > 0 and processing_time > 0:
            avg_lineups_per_sec = total_lineups_processed / processing_time
            print(
                f"  - Average processing speed: {avg_lineups_per_sec:.3f} lineups/second"
            )

        if files_processed > 0 and processing_time > 0:
            avg_time_per_file = processing_time / files_processed
            print(f"  - Average time per file: {avg_time_per_file:.3f} seconds")

        # Show map summary
        print("\nMaps summary:")
        for map_name, lineups in sorted(combined_data.items()):
            print(f"  - {map_name}: {len(lineups)} lineups")

    except Exception as e:
        print(f"Error saving {output_file}: {e}")


if __name__ == "__main__":
    # Configuration: Adjust these thresholds based on your needs
    POSITION_THRESHOLD = 10.0  # Maximum distance between positions (in game units)
    ANGLE_THRESHOLD = 5.0  # Maximum angle difference (in degrees)

    LOCS_FOLDER = "locs"  # Input folder containing JSON files
    OUTPUT_FILE = "Dupes_Removed_By_Frosty.json"  # Output JSON file

    print("CSGO Lineup Combiner Made By Frosty")
    print("=" * 50)
    print(f"Position threshold: {POSITION_THRESHOLD} units")
    print(f"Angle threshold: {ANGLE_THRESHOLD} degrees")
    print()
    
    time.sleep(5)  # Wait for 5 seconds before starting

    # Run the combination process
    combine_json_files(POSITION_THRESHOLD, ANGLE_THRESHOLD, LOCS_FOLDER, OUTPUT_FILE)

    print("\nProcess completed!")
