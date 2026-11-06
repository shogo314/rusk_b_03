use std::{
    fs,
    io::Write,
    path::PathBuf,
    process::{Command, Output, Stdio},
    sync::atomic::{AtomicUsize, Ordering},
};
static NEXT: AtomicUsize = AtomicUsize::new(0);
pub(crate) struct Case(pub(crate) PathBuf);
impl Case {
    pub(crate) fn new(source: &str) -> Self {
        let dir = std::env::temp_dir().join(format!(
            "rusk-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("main.rusk"), source).unwrap();
        Self(dir)
    }
    pub(crate) fn compile(&self) -> Output {
        Command::new(env!("CARGO_BIN_EXE_rusk"))
            .arg("compile")
            .arg(self.0.join("main.rusk"))
            .arg("-o")
            .arg(self.0.join("main.cpp"))
            .output()
            .unwrap()
    }
    pub(crate) fn run(&self, input: &str) -> Output {
        let compiled = self.compile();
        assert!(
            compiled.status.success(),
            "{}",
            String::from_utf8_lossy(&compiled.stderr)
        );
        let native = Command::new("g++")
            .args(["-std=c++20", "-O2", "-Wall", "-Wextra"])
            .arg(self.0.join("main.cpp"))
            .arg("-o")
            .arg(self.0.join("main"))
            .output()
            .unwrap();
        assert!(
            native.status.success(),
            "{}",
            String::from_utf8_lossy(&native.stderr)
        );
        self.execute(input)
    }
    pub(crate) fn execute(&self, input: &str) -> Output {
        let mut child = Command::new(self.0.join("main"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        child
            .stdin
            .take()
            .unwrap()
            .write_all(input.as_bytes())
            .unwrap();
        child.wait_with_output().unwrap()
    }
}
impl Drop for Case {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
