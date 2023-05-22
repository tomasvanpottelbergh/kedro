# Kedro plugins

Kedro plugins allow you to create new features for Kedro and inject additional commands into the CLI. Plugins are developed as separate Python packages that exist outside of any Kedro project.

## Overview

Kedro extension mechanism is built on [pluggy](https://pluggy.readthedocs.io/), a solid plugin management library that was created for the [pytest](https://docs.pytest.org/) ecosystem. pluggy relies on [entry points](https://packaging.python.org/en/latest/specifications/entry-points/), a Python mechanism for packages to provide components that can be discovered by other packages using [`importlib.metadata`](https://docs.python.org/3/library/importlib.metadata.html#entry-points).

## Example of a simple plugin

Here is a simple example of a plugin that prints the pipeline as JSON:

`kedrojson/plugin.py`

```python
import click
from kedro.framework.project import pipelines


@click.group(name="JSON")
def commands():
    pass


@commands.command()
@click.pass_obj
def to_json(metadata):
    """Display the pipeline in JSON format"""
    pipeline = pipelines["__default__"]
    print(pipeline.to_json())
```

The plugin provides the following `entry_points` config in `setup.py`:

```python
setup(
    entry_points={"kedro.project_commands": ["kedrojson = kedrojson.plugin:commands"]}
)
```

Once the plugin is installed, you can run it as follows:
```bash
kedro to_json
```

## Extend starter aliases
It is possible to extend the list of starter aliases built into Kedro. This means that a [custom Kedro starter](../kedro_project_setup/starters.md#how-to-create-a-kedro-starter) can be used directly through the `starter` argument in `kedro new` rather than needing to explicitly provide the `template` and `directory` arguments. A custom starter alias behaves in the same way as an official Kedro starter alias and is also picked up by `kedro starter list`.

You need to extend the starters by providing a list of  `KedroStarterSpec`, in this example it is defined in a file called `plugin.py`.

Example for a non-git repository starter:
```python
# plugin.py
starters = [
    KedroStarterSpec(
        alias="test_plugin_starter",
        template_path="your_local_directory/starter_folder",
    )
]
```

Example for a git repository starter:
```python
# plugin.py
starters = [
    KedroStarterSpec(
        alias="test_plugin_starter",
        template_path="https://github.com/kedro-org/kedro-starters/",
        directory="pandas-iris",
    )
]
```

The `directory` argument is optional and should be used when you have multiple templates in one repository as for the [official kedro-starters](https://github.com/kedro-org/kedro-starters). If you only have one template, your top-level directory will be treated as the template. For an example, see the [pandas-iris starter](https://github.com/kedro-org/kedro-starters/tree/main/pandas-iris).

In your `setup.py`, you need to register the specifications to `kedro.starters`.

```python
setup(
    entry_points={"kedro.starters": ["starter =  plugin:starters"]},
)
```

After that you can use this starter with `kedro new --starter=test_plugin_starter`.

```{note}
If your starter lives on a git repository, by default Kedro attempts to use a tag or branch labelled with your version of Kedro, e.g. `0.18.8.`. This means that you can host different versions of your starter template on the same repository, and the correct one will automatically be used. If you do not wish to follow this structure, you should override it with the `checkout` flag, e.g. `kedro new --starter=test_plugin_starter --checkout=main`.
```

## Working with `click`

Commands must be provided as [`click` `Groups`](https://click.palletsprojects.com/en/7.x/api/#click.Group)

The `click Group` will be merged into the main CLI Group. In the process, the options on the group are lost, as is any processing that was done as part of its callback function.


## Project context

When they run, plugins may request information about the current project by creating a session and loading its context:

```python
from pathlib import Path

from kedro.framework.startup import _get_project_metadata
from kedro.framework.session import KedroSession


project_path = Path.cwd()
session = KedroSession.create(project_path=project_path)
context = session.load_context()
```

## Initialisation

If the plugin initialisation needs to occur prior to Kedro starting, it can declare the `entry_point` key `kedro.init`. This entry point must refer to a function that currently has no arguments, but for future proofing you should declare it with `**kwargs`.

## `global` and `project` commands

Plugins may also add commands to the Kedro CLI, which supports two types of commands:

* _global_ - available both inside and outside a Kedro project. Global commands use the `entry_point` key `kedro.global_commands`.
* _project_ - available only when a Kedro project is detected in the current directory. Project commands use the `entry_point` key `kedro.project_commands`.

## Suggested command convention

We use the following command convention: `kedro <plugin-name> <command>`, with `kedro <plugin-name>` acting as a top-level command group. This is our suggested way of structuring your plugin bit it is not necessary for your plugin to work.

## Hooks

You can develop hook implementations and have them automatically registered to the project context when the plugin is installed. To enable this for your custom plugin, simply add the following entry in your `setup.py`:

```python
setup(entry_points={"kedro.hooks": ["plugin_name = plugin_name.plugin:hooks"]})
```

where `plugin.py` is the module where you declare hook implementations:

```python
import logging

from kedro.framework.hooks import hook_impl


class MyHooks:
    @hook_impl
    def after_catalog_created(self, catalog):  # pylint: disable=unused-argument
        logging.info("Reached after_catalog_created hook")


hooks = MyHooks()
```

```{note}
`hooks` should be an instance of the class defining the Hooks.
```

## CLI Hooks

You can also develop hook implementations to extend Kedro's CLI behaviour in your plugin. To find available CLI hooks, please visit [kedro.framework.cli.hooks](/kedro.framework.cli.hooks). To register CLI hooks developed in your plugin with Kedro, add the following entry in your project's `setup.py`:

```python
setup(entry_points={"kedro.cli_hooks": ["plugin_name = plugin_name.plugin:cli_hooks"]})
```

where `plugin.py` is the module where you declare hook implementations:

```python
import logging

from kedro.framework.cli.hooks import cli_hook_impl


class MyCLIHooks:
    @cli_hook_impl
    def before_command_run(self, project_metadata, command_args):
        logging.info(
            "Command %s will be run for project %s", command_args, project_metadata
        )


cli_hooks = MyCLIHooks()
```

## Contributing process

When you are ready to submit your code:

1. Create a separate repository using our naming convention for `plugin`s (`kedro-<plugin-name>`)
2. Choose a command approach: `global` and / or `project` commands:
   - All `global` commands should be provided as a single `click` group
   - All `project` commands should be provided as another `click` group
   - The `click` groups are declared through the [entry points mechanism](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)
3. Include a `README.md` describing your plugin's functionality and all dependencies that should be included
4. Use GitHub tagging to tag your plugin as a `kedro-plugin` so that we can find it

## Supported Kedro plugins

- [Kedro-Datasets](https://github.com/kedro-org/kedro-plugins/tree/main/kedro-datasets), a collection of all of Kedro's data connectors. These data
connectors are implementations of the `AbstractDataSet`
- [Kedro-Docker](https://github.com/kedro-org/kedro-plugins/tree/main/kedro-docker), a tool for packaging and shipping Kedro projects within containers
- [Kedro-Airflow](https://github.com/kedro-org/kedro-plugins/tree/main/kedro-airflow), a tool for converting your Kedro project into an Airflow project
- [Kedro-Viz](https://github.com/kedro-org/kedro-viz), a tool for visualising your Kedro pipelines


## Community-developed plugins

See the full list of plugins using the GitHub tag [kedro-plugin](https://github.com/topics/kedro-plugin).


```{note}
Your plugin needs to have an [Apache 2.0 compatible license](https://www.apache.org/legal/resolved.html#category-a) to be considered for this list.
```

- [Kedro-Pandas-Profiling](https://github.com/BrickFrog/kedro-pandas-profiling), by [Justin Malloy](https://github.com/BrickFrog), uses [Pandas Profiling](https://github.com/pandas-profiling/pandas-profiling) to profile datasets in the Kedro catalog
- [find-kedro](https://github.com/WaylonWalker/find-kedro), by [Waylon Walker](https://github.com/WaylonWalker), automatically constructs pipelines using `pytest`-style pattern matching
- [kedro-static-viz](https://github.com/WaylonWalker/kedro-static-viz), by [Waylon Walker](https://github.com/WaylonWalker), generates a static [Kedro-Viz](https://github.com/kedro-org/kedro-viz) site (HTML, CSS, JS)
- [steel-toes](https://github.com/WaylonWalker/steel-toes), by [Waylon Walker](https://github.com/WaylonWalker), prevents stepping on toes by automatically branching data paths
- [kedro-wings](https://github.com/tamsanh/kedro-wings), by [Tam-Sanh Nguyen](https://github.com/tamsanh), simplifies and speeds up pipeline creation by auto-generating catalog datasets
- [kedro-great](https://github.com/tamsanh/kedro-great), by [Tam-Sanh Nguyen](https://github.com/tamsanh), integrates Kedro with [Great Expectations](https://greatexpectations.io), enabling catalog-based expectation generation and data validation on pipeline run
- [Kedro-Accelerator](https://github.com/deepyaman/kedro-accelerator), by [Deepyaman Datta](https://github.com/deepyaman), speeds up pipelines by parallelizing I/O in the background
- [kedro-dataframe-dropin](https://github.com/mzjp2/kedro-dataframe-dropin), by [Zain Patel](https://github.com/mzjp2), lets you swap out pandas datasets for modin or RAPIDs equivalents for specialised use to speed up your workflows (e.g on GPUs)
- [kedro-mlflow](https://github.com/Galileo-Galilei/kedro-mlflow), by [Yolan Honoré-Rougé](https://github.com/galileo-galilei) and [Takieddine Kadiri](https://github.com/takikadiri), facilitates [MLflow](https://www.mlflow.org/) integration within a Kedro project. Its main features are modular configuration, automatic parameters tracking, datasets versioning, Kedro pipelines packaging and serving and automatic synchronization between training and inference pipelines for high reproducibility of machine learning experiments and ease of deployment. A tutorial is provided in the [kedro-mlflow-tutorial repo](https://github.com/Galileo-Galilei/kedro-mlflow-tutorial). You can find more information in the [kedro-mlflow documentation](https://kedro-mlflow.readthedocs.io/en/stable/).
- [Kedro-Neptune](https://github.com/neptune-ai/kedro-neptune), by [Jakub Czakon](https://github.com/jakubczakon) and [Rafał Jankowski](https://github.com/Raalsky), lets you have all the benefits of a nicely organized Kedro pipeline with Neptune: a powerful user interface built for ML metadata management. It lets you browse and filter pipeline executions, compare nodes and pipelines on metrics and parameters, and visualize pipeline metadata like learning curves, node outputs, and charts. For more information, tutorials and videos, go to the [Kedro-Neptune documentation](https://docs.neptune.ai/integrations-and-supported-tools/automation-pipelines/kedro).
- [kedro-dolt](https://www.dolthub.com/blog/2021-06-16-kedro-dolt-plugin/), by [Max Hoffman](https://github.com/max-hoffman) and [Oscar Batori](https://github.com/oscarbatori), allows you to expand the data versioning abilities of data scientists and engineers
- [kedro-kubeflow](https://github.com/getindata/kedro-kubeflow), by [GetInData](https://github.com/getindata), lets you run and schedule pipelines on Kubernetes clusters using [Kubeflow Pipelines](https://www.kubeflow.org/docs/components/pipelines/overview/)
- [kedro-airflow-k8s](https://github.com/getindata/kedro-airflow-k8s), by [GetInData](https://github.com/getindata), enables running a Kedro pipeline with Airflow on a Kubernetes cluster
- [kedro-vertexai](https://github.com/getindata/kedro-vertexai), by [GetInData](https://github.com/getindata), enables running a Kedro pipeline with Vertex AI Pipelines service
- [kedro-azureml](https://github.com/getindata/kedro-azureml), by [GetInData](https://github.com/getindata), enables running a Kedro pipeline with Azure ML Pipelines service
- [kedro-sagemaker](https://github.com/getindata/kedro-sagemaker), by [GetInData](https://github.com/getindata), enables running a Kedro pipeline with Amazon SageMaker service
- [kedro-partitioned](https://github.com/ProjetaAi/kedro-partitioned), by [Gabriel Daiha Alves](https://github.com/gabrieldaiha) and [Nickolas da Rocha Machado](https://github.com/nickolasrm), extends the functionality on processing partitioned data.
- [kedro-auto-catalog](https://github.com/WaylonWalker/kedro-auto-catalog), by [Waylon Walker](https://github.com/WaylonWalker) A configurable replacement for `kedro catalog create` that allows you to create default dataset types other than MemoryDataset.
