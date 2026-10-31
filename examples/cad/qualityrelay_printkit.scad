// QualityRelay 5.0 rebuilt print kit
// Units: millimeters
// Export one part at a time by changing `part`.
// slot_defect / tab_defect are seeded out-of-tolerance specimens that cannot fit any
// mating part in this kit (CAD interference >= 0.40 mm). They are intentional test
// specimens, not naturally occurring manufacturing defects.

part = "slot_good";

coupon_length = 60;
coupon_height = 6;
slot_base_length = 12;
slot_rail_width = 6;

module slot_coupon(inner_width) {
    outer_width = inner_width + 2 * slot_rail_width;
    union() {
        cube([slot_base_length, outer_width, coupon_height]);
        translate([slot_base_length, 0, 0])
            cube([coupon_length - slot_base_length, slot_rail_width, coupon_height]);
        translate([slot_base_length, slot_rail_width + inner_width, 0])
            cube([coupon_length - slot_base_length, slot_rail_width, coupon_height]);
    }
}

module tab_coupon(width) {
    cube([coupon_length, width, coupon_height]);
}

if (part == "slot_good") {
    slot_coupon(21.20);
} else if (part == "slot_nominal") {
    slot_coupon(21.00);
} else if (part == "slot_risk") {
    slot_coupon(20.70);
} else if (part == "tab_good") {
    tab_coupon(19.80);
} else if (part == "tab_nominal") {
    tab_coupon(20.00);
} else if (part == "tab_risk") {
    tab_coupon(20.30);
} else if (part == "slot_defect") {
    slot_coupon(19.40);
} else if (part == "tab_defect") {
    tab_coupon(21.60);
} else if (part == "repeatability_bar") {
    tab_coupon(20.00);
} else {
    assert(false, str("Unknown part: ", part));
}
