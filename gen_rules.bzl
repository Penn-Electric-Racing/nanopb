load("@com_google_protobuf//:protobuf.bzl", "proto_gen")

def cc_nanopb_gen_impl_(ctx):
    proto_library = ctx.files.proto_library[0]
    nanopb_python_binary = ctx.executable.nanopb_python_binary

    args = ctx.actions.args()
    args.add_all(['-e', '.nanopb', '-F', ctx.attr.gen_base])
    args.add_all(['--strip-path'])
    args.add_all(['--output-dir', ctx.outputs.gen_src.dirname])
    args.add(proto_library)
    ctx.actions.run(outputs=[ctx.outputs.gen_src, ctx.outputs.gen_hdr],
                    executable=nanopb_python_binary,
                    inputs=[proto_library],
                    arguments=[args])

cc_nanopb_gen = rule(
    implementation=cc_nanopb_gen_impl_,
    attrs = {
        'proto_library': attr.label(),
        'nanopb_python_binary': attr.label(
                executable=True,
                cfg="host",
                mandatory=True),
        'gen_base': attr.string(mandatory=True),
        'gen_src': attr.output(mandatory=True),
        'gen_hdr': attr.output(mandatory=True)
    }
)

# hdr_filename/src_filename can't be predicted!
def cc_nanopb_library(name, proto_library, base_name,
                      deps=[], # should be other cc_nanopb_library targets!
                      includes=[], visibility=[]):
    src_filename = base_name + '.nanopb.c'
    hdr_filename = base_name + '.nanopb.h'

    cc_nanopb_gen(
        name=name + '_gen',
        nanopb_python_binary="@com_github_nanopb_nanopb//:nanopb_generate_main",
        proto_library=proto_library,
        visibility=visibility,
        gen_base=base_name,
        gen_src=base_name + '.nanopb.c',
        gen_hdr=base_name + '.nanopb.h'
    )

    native.cc_library(
        name = name,
        srcs = [src_filename],
        hdrs = [hdr_filename],
        includes = includes,
        deps = deps + ["@com_github_nanopb_nanopb//:nanopb"],
        visibility=visibility
    )
