import textwrap
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


class ActionConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (REPO_ROOT / "action.yml").open(encoding="utf-8") as handle:
            cls.action = yaml.safe_load(handle)
        cls.steps = cls.action["runs"]["steps"]

    def step(self, name):
        for step in self.steps:
            if step.get("name") == name:
                return step
        self.fail(f"Missing step: {name}")

    def script(self, name):
        return textwrap.dedent(self.step(name)["run"]).strip()

    def test_action_is_a_composite_action_with_expected_inputs(self):
        self.assertEqual(self.action["name"], "build-paper")
        self.assertEqual(
            self.action["description"],
            "Build a Jupyter ipynb file into a PDF and a GitHub Page",
        )
        self.assertEqual(self.action["runs"]["using"], "composite")

        expected_inputs = {
            "filename": {"required": True, "default": "paper.ipynb"},
            "requirements-txt": {"required": True, "default": "requirements.txt"},
            "publish-ghpages": {"required": True, "default": False},
            "python-version": {"required": True, "default": "3.10"},
            "pandoc-version": {"required": True, "default": "2.19"},
            "attachments": {"required": True, "default": ""},
            "build-pdf": {"required": True, "default": True},
        }

        self.assertEqual(set(self.action["inputs"]), set(expected_inputs))
        for input_name, expected in expected_inputs.items():
            with self.subTest(input_name=input_name):
                self.assertEqual(
                    self.action["inputs"][input_name]["required"], expected["required"]
                )
                self.assertEqual(
                    self.action["inputs"][input_name]["default"], expected["default"]
                )

    def test_setup_steps_bind_tool_versions_to_inputs(self):
        self.assertEqual(self.step("Install TeX Live")["if"], "${{ inputs.build-pdf }}")
        self.assertEqual(
            self.step("install missing fonts for PDF generation")["if"],
            "${{ inputs.build-pdf }}",
        )
        self.assertEqual(self.step("build - the paper - PDF")["if"], "${{ inputs.build-pdf }}")
        self.assertEqual(self.step("Copy PDF to _site")["if"], "${{ inputs.build-pdf }}")

        python_setup = next(
            step
            for step in self.steps
            if step.get("uses", "").startswith("actions/setup-python@")
        )
        self.assertEqual(
            python_setup["with"]["python-version"], "${{ inputs.python-version }}"
        )

        pandoc_setup = next(
            step for step in self.steps if step.get("uses") == "pandoc/actions/setup@main"
        )
        self.assertEqual(pandoc_setup["with"]["version"], "${{ inputs.pandoc-version }}")

    def test_prerequisite_installation_creates_a_venv_and_installs_both_requirement_sets(self):
        script = self.script("build the paper - install prerequisites")

        self.assertIn("python3 -m venv .venv", script)
        self.assertIn(". .venv/bin/activate", script)
        self.assertIn("pip install -U pip", script)
        self.assertIn("pip install -Ur ${{ github.action_path }}/requirements.txt", script)
        self.assertIn("pip install -Ur ${{inputs.requirements-txt}}", script)

    def test_html_build_executes_the_notebook_and_generates_site_index(self):
        script = self.script("build - the paper - HTML")

        expected_lines = [
            "python3 -m venv .venv",
            ". .venv/bin/activate",
            "jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace ${{inputs.filename}}",
            "jupyter nbconvert --execute --to notebook --inplace ${{inputs.filename}}",
            "jupyter nbconvert ${{inputs.filename}} --TagRemovePreprocessor.remove_input_tags='html_only' --TagRemovePreprocessor.remove_cell_tags='latex_only' --TagRemovePreprocessor.remove_cell_tags='no_html' --to html --template classic --output-dir _site --output index",
            "jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace ${{inputs.filename}}",
        ]
        self.assertEqual(script.splitlines(), expected_lines)

    def test_pdf_build_uses_pdf_specific_filters_and_restores_a_clean_notebook(self):
        script = self.script("build - the paper - PDF")

        expected_lines = [
            "python3 -m venv .venv",
            ". .venv/bin/activate",
            "jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace ${{inputs.filename}}",
            "jupyter nbconvert --execute --to notebook --inplace ${{inputs.filename}}",
            "jupyter nbconvert ${{inputs.filename}} --TagRemovePreprocessor.remove_input_tags='latex_only' --TagRemovePreprocessor.remove_cell_tags='html_only' --TagRemovePreprocessor.remove_cell_tags='no_latex' --to pdf",
            "jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace ${{inputs.filename}}",
        ]
        self.assertEqual(script.splitlines(), expected_lines)

    def test_optional_attachment_copy_step_copies_each_attachment_into_the_site_directory(self):
        step = self.step("Copy attachments")

        self.assertEqual(step["if"], "${{ inputs.attachments != '' }}")
        self.assertEqual(
            self.script("Copy attachments").splitlines(),
            ["for f in ${{ inputs.attachments }}; do", "cp ${f} _site", "done"],
        )

    def test_pdf_copy_logic_derives_the_output_name_from_the_notebook_filename(self):
        script = self.script("Copy PDF to _site")

        self.assertEqual(
            script.splitlines(),
            [
                'PDF_FILE="${{ inputs.filename }}"',
                'PDF_FILE="${PDF_FILE%.ipynb}.pdf"',
                'if [ -f "$PDF_FILE" ]; then',
                '  cp "$PDF_FILE" _site/',
                "fi",
            ],
        )

    def test_publish_and_artifact_steps_target_the_generated_site(self):
        publish_step = self.step("Publish to GH Pages")
        self.assertEqual(publish_step["if"], "${{ inputs.publish-ghpages == 'true' }}")
        self.assertEqual(
            self.script("Publish to GH Pages").splitlines(),
            [". .venv/bin/activate", "ghp-import -n -p -f _site"],
        )

        artifact_step = self.step("publish artifacts")
        self.assertTrue(artifact_step["uses"].startswith("actions/upload-artifact@"))
        self.assertEqual(artifact_step["with"]["name"], "paper")
        self.assertEqual(artifact_step["with"]["path"], "_site")
        self.assertEqual(
            artifact_step["env"]["FORCE_JAVASCRIPT_ACTIONS_TO_NODE24"], True
        )


if __name__ == "__main__":
    unittest.main()
