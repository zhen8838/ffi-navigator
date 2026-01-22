import os
from .. import pattern
from ..util import normalize_path
from .tvm import TVMProvider, BaseProvider


class TilelangProvider(TVMProvider):
  def __init__(self, resolver, logger=None):
    super().__init__(resolver, logger)
    self.dialect_name = "tilelang"

    self.py_reg_object = pattern.decorator_matcher(
        ["register_object", "register_node", "register_relay_node"], "class",
        lambda key, path, rg, reg:
        pattern.Ref(key="relay." + key, path=path, range=rg)
        if reg.endswith("relay_node")
        else pattern.Ref(key=key, path=path, range=rg))

    self.py_init_api = pattern.macro_matcher(
        ["tvm.ffi._init_api", "_init_api", "tvm_ffi.init_ffi_api", "init_ffi_api"],
        lambda key, path, _, reg: self._wrap_py_init_api(key, path, reg))

    self.tl_cc_def_op = pattern.re_matcher(
        r"(?P<macro_name>(TIR_REGISTER_TL_OP|TIR_REGISTER_TL_TILE_OP))\((?P<key>[^,]+)\)?",
        lambda match, path, rg:
        pattern.Def(key="tl." + match.group("key"), path=path, range=rg))

  def _cc_extract(self, path, source, begin, end):
    results = super()._cc_extract(path, source, begin, end)
    results += self.tl_cc_def_op(path, source, begin, end)
    return results

  def get_additional_scan_dirs(self, root_path):
    return [
        os.path.join(root_path, "tilelang"),
    ]

  def init_pass(self, path, source):
    if path.endswith(normalize_path("tilelang/__init__.py")):
      self._pypath_root = os.path.abspath(path[:-len("/__init__.py")])
      self.resolver.add_package(self.dialect_name, self._pypath_root)
      self._pypath_init = os.path.abspath(path[:-len(".py")])
      self.logger.info("%s: found python path %s", self.dialect_name, self._pypath_root)
      # self._pypath_funcmod = os.path.join(self._pypath_root, "_ffi", "function")
      # self._pypath_api_internal = os.path.join(self._pypath_root, "_api_internal")

  def _wrap_py_init_api(self, key, path, reg):
      if reg != "tvm.ffi._init_api" and reg != "tvm_ffi.init_ffi_api":
          # legacy behavior
          new_mod, new_name = self.resolver.resolve(path, "_init_api")
          if new_mod != self._pypath_funcmod or new_name != "_init_api":
              return None
      prefix = key[4:] if key.startswith("tvm.") else key
      fkey2var = lambda k : k[len(prefix) + 1:]
      fvar2key = lambda v : prefix + "." + v

      return pattern.Export(key_prefix=prefix, path=path,
                            fvar2key=fvar2key,
                            fkey2var=fkey2var)
