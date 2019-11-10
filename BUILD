cc_library(
  name = "nanopb",
  hdrs = [
    "pb.h",
    "pb_common.h",
    "pb_decode.h",
    "pb_encode.h",
  ],
  srcs = [
    "pb_common.c",
    "pb_decode.c",
    "pb_encode.c",
  ],
  visibility = ["//visibility:public"],
)

py_library(
    name = "nanopb_generate",
    srcs = glob(["generator/**/*.py"])
)

py_binary(
    name = "nanopb_generate_main",
    srcs = ["generator/nanopb_generator.py"],
    main = "generator/nanopb_generator.py",
    deps = ["@com_google_protobuf//:protobuf_python", ":nanopb_generate"],
    visibility = ["//visibility:public"],
)
