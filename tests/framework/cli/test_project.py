# pylint: disable=unused-argument
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from kedro.framework.cli.project import NO_DEPENDENCY_MESSAGE


@pytest.fixture(autouse=True)
def call_mock(mocker):
    return mocker.patch("kedro.framework.cli.project.call")


@pytest.fixture(autouse=True)
def python_call_mock(mocker):
    return mocker.patch("kedro.framework.cli.project.python_call")


@pytest.fixture
def fake_copyfile(mocker):
    return mocker.patch("shutil.copyfile")


@pytest.mark.usefixtures("chdir_to_dummy_project")
class TestActivateNbstripoutCommand:
    @staticmethod
    @pytest.fixture()
    def fake_nbstripout():
        """
        ``nbstripout`` tries to access ``sys.stdin.buffer.readable``
        on import, but it's patches by pytest.
        Let's replace it by the fake!
        """
        sys.modules["nbstripout"] = "fake"
        yield
        del sys.modules["nbstripout"]

    @staticmethod
    @pytest.fixture
    def fake_git_repo(mocker):
        return mocker.patch("subprocess.run", return_value=mocker.Mock(returncode=0))

    @staticmethod
    @pytest.fixture
    def without_git_repo(mocker):
        return mocker.patch("subprocess.run", return_value=mocker.Mock(returncode=1))

    def test_install_successfully(
        self, fake_project_cli, call_mock, fake_nbstripout, fake_git_repo, fake_metadata
    ):
        result = CliRunner().invoke(
            fake_project_cli, ["activate-nbstripout"], obj=fake_metadata
        )
        assert not result.exit_code

        call_mock.assert_called_once_with(["nbstripout", "--install"])

        fake_git_repo.assert_called_once_with(
            ["git", "rev-parse", "--git-dir"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_nbstripout_not_installed(
        self, fake_project_cli, fake_git_repo, mocker, fake_metadata
    ):
        """
        Run activate-nbstripout target without nbstripout installed
        There should be a clear message about it.
        """
        mocker.patch.dict("sys.modules", {"nbstripout": None})

        result = CliRunner().invoke(
            fake_project_cli, ["activate-nbstripout"], obj=fake_metadata
        )
        assert result.exit_code
        assert "nbstripout is not installed" in result.stdout

    def test_no_git_repo(
        self, fake_project_cli, fake_nbstripout, without_git_repo, fake_metadata
    ):
        """
        Run activate-nbstripout target with no git repo available.
        There should be a clear message about it.
        """
        result = CliRunner().invoke(
            fake_project_cli, ["activate-nbstripout"], obj=fake_metadata
        )

        assert result.exit_code
        assert "Not a git repository" in result.stdout

    def test_no_git_executable(
        self, fake_project_cli, fake_nbstripout, mocker, fake_metadata
    ):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        result = CliRunner().invoke(
            fake_project_cli, ["activate-nbstripout"], obj=fake_metadata
        )

        assert result.exit_code
        assert "Git executable not found. Install Git first." in result.stdout


@pytest.mark.usefixtures("chdir_to_dummy_project")
class TestTestCommand:
    def test_happy_path(self, fake_project_cli, python_call_mock):
        result = CliRunner().invoke(fake_project_cli, ["test", "--random-arg", "value"])
        assert not result.exit_code
        python_call_mock.assert_called_once_with("pytest", ("--random-arg", "value"))

    def test_pytest_not_installed(
        self, fake_project_cli, python_call_mock, mocker, fake_repo_path, fake_metadata
    ):
        mocker.patch.dict("sys.modules", {"pytest": None})

        result = CliRunner().invoke(
            fake_project_cli, ["test", "--random-arg", "value"], obj=fake_metadata
        )
        expected_message = NO_DEPENDENCY_MESSAGE.format(
            module="pytest", src=str(fake_repo_path / "src")
        )

        assert result.exit_code
        assert expected_message in result.stdout
        python_call_mock.assert_not_called()


@pytest.mark.usefixtures("chdir_to_dummy_project")
class TestLintCommand:
    @pytest.mark.parametrize("files", [(), ("src",)])
    def test_lint(
        self,
        fake_project_cli,
        python_call_mock,
        files,
        mocker,
        fake_repo_path,
        fake_metadata,
    ):
        mocker.patch("kedro.framework.cli.project._check_module_importable")
        result = CliRunner().invoke(
            fake_project_cli, ["lint", *files], obj=fake_metadata
        )
        assert not result.exit_code, result.stdout

        expected_files = files or (
            str(fake_repo_path / "src/tests"),
            str(fake_repo_path / "src/dummy_package"),
        )
        expected_calls = [
            mocker.call("black", expected_files),
            mocker.call("flake8", expected_files),
            mocker.call("isort", expected_files),
        ]

        assert python_call_mock.call_args_list == expected_calls

    @pytest.mark.parametrize(
        "check_flag,files",
        [
            ("-c", ()),
            ("--check-only", ()),
            ("-c", ("src",)),
            ("--check-only", ("src",)),
        ],
    )
    def test_lint_check_only(
        self,
        fake_project_cli,
        python_call_mock,
        check_flag,
        mocker,
        files,
        fake_repo_path,
        fake_metadata,
    ):
        mocker.patch("kedro.framework.cli.project._check_module_importable")
        result = CliRunner().invoke(
            fake_project_cli, ["lint", check_flag, *files], obj=fake_metadata
        )
        assert not result.exit_code, result.stdout

        expected_files = files or (
            str(fake_repo_path / "src/tests"),
            str(fake_repo_path / "src/dummy_package"),
        )
        expected_calls = [
            mocker.call("black", ("--check",) + expected_files),
            mocker.call("flake8", expected_files),
            mocker.call("isort", ("--check",) + expected_files),
        ]

        assert python_call_mock.call_args_list == expected_calls

    @pytest.mark.parametrize(
        "module_name,side_effects",
        [("flake8", [ImportError, None, None]), ("isort", [None, ImportError, None])],
    )
    def test_import_not_installed(
        self,
        fake_project_cli,
        python_call_mock,
        module_name,
        side_effects,
        mocker,
        fake_repo_path,
        fake_metadata,
    ):
        # pretending we have the other linting dependencies, but not the <module_name>
        mocker.patch(
            "kedro.framework.cli.utils.import_module", side_effect=side_effects
        )

        result = CliRunner().invoke(fake_project_cli, ["lint"], obj=fake_metadata)
        expected_message = NO_DEPENDENCY_MESSAGE.format(
            module=module_name, src=str(fake_repo_path / "src")
        )

        assert result.exit_code, result.stdout
        assert expected_message in result.stdout
        python_call_mock.assert_not_called()

    def test_pythonpath_env_var(
        self, fake_project_cli, mocker, fake_repo_path, fake_metadata
    ):
        mocked_environ = mocker.patch("os.environ", {})
        CliRunner().invoke(fake_project_cli, ["lint"], obj=fake_metadata)
        assert mocked_environ == {"PYTHONPATH": str(fake_repo_path / "src")}


@pytest.mark.usefixtures("chdir_to_dummy_project")
class TestIpythonCommand:
    def test_happy_path(
        self,
        call_mock,
        fake_project_cli,
        fake_repo_path,
        fake_metadata,
    ):
        result = CliRunner().invoke(
            fake_project_cli, ["ipython", "--random-arg", "value"], obj=fake_metadata
        )
        assert not result.exit_code, result.stdout
        call_mock.assert_called_once_with(
            [
                "ipython",
                "--ext",
                "kedro.ipython",
                "--random-arg",
                "value",
            ]
        )

    @pytest.mark.parametrize("env_flag,env", [("--env", "base"), ("-e", "local")])
    def test_env(
        self,
        env_flag,
        env,
        fake_project_cli,
        mocker,
        fake_metadata,
    ):
        """This tests starting ipython with specific env."""
        mock_environ = mocker.patch("os.environ", {})
        result = CliRunner().invoke(
            fake_project_cli, ["ipython", env_flag, env], obj=fake_metadata
        )
        assert not result.exit_code, result.stdout
        assert mock_environ["KEDRO_ENV"] == env

    def test_fail_no_ipython(self, fake_project_cli, mocker):
        mocker.patch.dict("sys.modules", {"IPython": None})
        result = CliRunner().invoke(fake_project_cli, ["ipython"])

        assert result.exit_code
        error = (
            "Module 'IPython' not found. Make sure to install required project "
            "dependencies by running the 'pip install -r src/requirements.txt' command first."
        )
        assert error in result.output


@pytest.mark.usefixtures("chdir_to_dummy_project")
class TestPackageCommand:
    def test_happy_path(
        self, call_mock, fake_project_cli, mocker, fake_repo_path, fake_metadata
    ):
        result = CliRunner().invoke(fake_project_cli, ["package"], obj=fake_metadata)
        assert not result.exit_code, result.stdout
        call_mock.assert_has_calls(
            [
                mocker.call(
                    [
                        sys.executable,
                        "-m",
                        "build",
                        "--wheel",
                        "--outdir",
                        "../dist",
                    ],
                    cwd=str(fake_repo_path / "src"),
                ),
                mocker.call(
                    [
                        "tar",
                        "--exclude=local/*.yml",
                        "-czf",
                        f"dist/conf-{fake_metadata.package_name}.tar.gz",
                        f"--directory={fake_metadata.project_path}",
                        "conf",
                    ],
                ),
            ]
        )


@pytest.mark.usefixtures("chdir_to_dummy_project")
class TestBuildDocsCommand:
    def test_happy_path(
        self,
        call_mock,
        python_call_mock,
        fake_project_cli,
        mocker,
        fake_repo_path,
        fake_metadata,
    ):
        fake_rmtree = mocker.patch("shutil.rmtree")

        result = CliRunner().invoke(fake_project_cli, ["build-docs"], obj=fake_metadata)
        assert not result.exit_code, result.stdout
        call_mock.assert_has_calls(
            [
                mocker.call(
                    [
                        "sphinx-apidoc",
                        "--module-first",
                        "-o",
                        "docs/source",
                        str(fake_repo_path / "src/dummy_package"),
                    ]
                ),
                mocker.call(
                    ["sphinx-build", "-M", "html", "docs/source", "docs/build", "-a"]
                ),
            ]
        )
        python_call_mock.assert_has_calls(
            [
                mocker.call("pip", ["install", str(fake_repo_path / "src/[docs]")]),
                mocker.call(
                    "pip",
                    ["install", "-r", str(fake_repo_path / "src/requirements.txt")],
                ),
                mocker.call("ipykernel", ["install", "--user", "--name=dummy_package"]),
            ]
        )
        fake_rmtree.assert_called_once_with("docs/build", ignore_errors=True)

    @pytest.mark.parametrize("open_flag", ["-o", "--open"])
    def test_open_docs(self, open_flag, fake_project_cli, mocker, fake_metadata):
        mocker.patch("shutil.rmtree")
        patched_browser = mocker.patch("webbrowser.open")
        result = CliRunner().invoke(
            fake_project_cli, ["build-docs", open_flag], obj=fake_metadata
        )
        assert not result.exit_code, result.stdout
        expected_path = (Path.cwd() / "docs" / "build" / "html" / "index.html").as_uri()
        patched_browser.assert_called_once_with(expected_path)


@pytest.mark.usefixtures("chdir_to_dummy_project", "fake_copyfile")
class TestBuildReqsCommand:
    def test_compile_from_requirements_file(
        self,
        python_call_mock,
        fake_project_cli,
        mocker,
        fake_repo_path,
        fake_copyfile,
        fake_metadata,
    ):
        # File exists:
        mocker.patch.object(Path, "is_file", return_value=True)

        result = CliRunner().invoke(fake_project_cli, ["build-reqs"], obj=fake_metadata)
        assert not result.exit_code, result.stdout
        assert "Requirements built!" in result.stdout

        python_call_mock.assert_called_once_with(
            "piptools",
            [
                "compile",
                str(fake_repo_path / "src" / "requirements.txt"),
                "--output-file",
                str(fake_repo_path / "src" / "requirements.lock"),
            ],
        )

    def test_compile_from_input_and_to_output_file(
        self,
        python_call_mock,
        fake_project_cli,
        fake_repo_path,
        fake_copyfile,
        fake_metadata,
    ):
        # File exists:
        input_file = fake_repo_path / "src" / "dev-requirements.txt"
        with open(input_file, "a", encoding="utf-8") as file:
            file.write("")
        output_file = fake_repo_path / "src" / "dev-requirements.lock"

        result = CliRunner().invoke(
            fake_project_cli,
            [
                "build-reqs",
                "--input-file",
                str(input_file),
                "--output-file",
                str(output_file),
            ],
            obj=fake_metadata,
        )
        assert not result.exit_code, result.stdout
        assert "Requirements built!" in result.stdout
        python_call_mock.assert_called_once_with(
            "piptools",
            ["compile", str(input_file), "--output-file", str(output_file)],
        )

    @pytest.mark.parametrize(
        "extra_args", [["--generate-hashes"], ["-foo", "--bar", "baz"]]
    )
    def test_extra_args(
        self,
        python_call_mock,
        fake_project_cli,
        fake_repo_path,
        extra_args,
        fake_metadata,
    ):
        requirements_txt = fake_repo_path / "src" / "requirements.txt"

        result = CliRunner().invoke(
            fake_project_cli, ["build-reqs"] + extra_args, obj=fake_metadata
        )

        assert not result.exit_code, result.stdout
        assert "Requirements built!" in result.stdout

        call_args = (
            ["compile"]
            + extra_args
            + [str(requirements_txt)]
            + ["--output-file", str(fake_repo_path / "src" / "requirements.lock")]
        )
        python_call_mock.assert_called_once_with("piptools", call_args)

    @pytest.mark.parametrize("os_name", ["posix", "nt"])
    def test_missing_requirements_txt(
        self, fake_project_cli, mocker, fake_metadata, os_name, fake_repo_path
    ):
        """Test error when input file requirements.txt doesn't exists."""
        requirements_txt = fake_repo_path / "src" / "requirements.txt"

        mocker.patch("kedro.framework.cli.project.os").name = os_name
        mocker.patch.object(Path, "is_file", return_value=False)
        result = CliRunner().invoke(fake_project_cli, ["build-reqs"], obj=fake_metadata)
        assert result.exit_code  # Error expected
        assert isinstance(result.exception, FileNotFoundError)
        assert f"File '{requirements_txt}' not found" in str(result.exception)
