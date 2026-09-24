import App from "./App";

type TaskStudioPluginProps = {
  dagId?: string;
  taskId?: string;
  runId?: string;
  mapIndex?: number;
};

export default function TaskStudioPlugin(
  props: TaskStudioPluginProps
) {
  return <App pluginContext={props} />;
}